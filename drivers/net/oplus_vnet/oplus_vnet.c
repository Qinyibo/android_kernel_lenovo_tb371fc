/***********************************************************
** Copyright (C), 2008-2021, oplus Mobile Comm Corp., Ltd.
** File: oplus_vnet.c
** Description: Add virtuan network for data shareds.
**
** Version: 1.0
** Date : 2022/8/12
**
** ------------------ Revision History:------------------------
** <author> <data> <version > <desc>
****************************************************************/

#include <linux/module.h>
#include <linux/kernel.h>
#include <linux/netdevice.h>
#include <linux/etherdevice.h>
#include <linux/init.h>
#include <linux/interrupt.h>
#include <linux/moduleparam.h>
#include <linux/version.h>
#include <net/pkt_sched.h>
#include <net/net_namespace.h>
#include <linux/netfilter.h>
#include <linux/netfilter_ipv4.h>
#include <linux/netfilter_ipv6.h>
#include <linux/skbuff.h>
#include <linux/spinlock.h>
#include <linux/ip.h>
#include <linux/ipv6.h>
#include <net/neighbour.h>
#include <net/ipv6.h>

#if (LINUX_VERSION_CODE < KERNEL_VERSION(6, 1, 0))
static int s_debug = 0;
static int s_enable = 1;

#define MAX_TXQUEUE_LEN 500


#define logi(fmt, args...) \
	do { \
		if (s_debug) { \
			printk("OVNET:" fmt "\n", ##args); \
		} \
	} while (0)

#define logk(fmt, args...) \
	do { \
		printk("OVNET:" fmt "\n", ##args); \
	} while (0)


enum {
	IFLA_OVNET_UNSPEC,
	IFLA_OVNET_BIND,
	IFLA_OVNET_PEER,
	IFLA_OVNET_PEER6,
	__IFLA_OVNET_MAX,
};

#define IFLA_OVNET_MAX (__IFLA_OVNET_MAX - 1)

#define VIRTUAL_NET_MAX 16

struct ovnet_dev_private {
	u32 bind_if;
	u32 peer_ip;
	struct in6_addr peer_ip6;
	spinlock_t peer_lock;
	struct net_device *bind_dev;
	struct nf_hook_ops nf_ops;
};

struct ovnet_if_kv {
	struct net *net; /* A device index is local to its network namespace. */
	u32 ovnet_if;
	u32 org_if;
};

static struct ovnet_if_kv s_if_map[VIRTUAL_NET_MAX];
static int s_used_count = 0;
static spinlock_t s_if_lock;

static int get_ovnet_if_by_org(struct net *net, u32 org_if, u32 *ovnet_if)
{
	int i = 0;

	if (org_if <= 0) {
		return -1;
	}

	spin_lock_bh(&s_if_lock);
	for (i = 0; i < VIRTUAL_NET_MAX; i++) {
		if (s_if_map[i].net == net && s_if_map[i].org_if == org_if) {
			*ovnet_if = s_if_map[i].ovnet_if;
			spin_unlock_bh(&s_if_lock);
			return 0;
		}
	}
	spin_unlock_bh(&s_if_lock);

	return -1;
}


static int update_ovnet_org_if(struct net *net, u32 org_if, u32 ovnet_if)
{
	int ret = -1;
	int i = 0;
	int first_usable = -1;

	spin_lock_bh(&s_if_lock);
	for (i = 0; i < VIRTUAL_NET_MAX; i++) {
		if (s_if_map[i].ovnet_if == 0) {
			if (first_usable == -1) {
				first_usable = i;
			}
		} else if (s_if_map[i].net == net && s_if_map[i].ovnet_if == ovnet_if) {
			if (s_if_map[i].org_if != org_if) {
				logk("ifmap update!!! ");
				s_if_map[i].org_if = org_if;
			} else {
				logk("ifmap not update!!! ");
			}
			spin_unlock_bh(&s_if_lock);
			return 0;
		} else if (s_if_map[i].net == net && s_if_map[i].org_if == org_if) {
			/* One ingress target per underlying device; never silently steal it. */
			spin_unlock_bh(&s_if_lock);
			return -EBUSY;
		}
	}

	if (first_usable != -1) {
		s_if_map[first_usable].net = net;
		s_if_map[first_usable].ovnet_if = ovnet_if;
		s_if_map[first_usable].org_if = org_if;
		s_used_count++;
		ret = 0;
	} else {
		logk("unavailable position for new key-value");
	}

	spin_unlock_bh(&s_if_lock);
	return ret;
}

static int del_if_map_by_ovnet(struct net *net, u32 ovnet_if)
{
	int i = 0;

	spin_lock_bh(&s_if_lock);
	for (i = 0; i < VIRTUAL_NET_MAX; i++) {
		if (s_if_map[i].net == net && s_if_map[i].ovnet_if == ovnet_if) {
			s_if_map[i].net = NULL;
			s_if_map[i].org_if = 0;
			s_if_map[i].ovnet_if = 0;
			s_used_count--;
			break;
		}
	}

	spin_unlock_bh(&s_if_lock);
	return 0;
}


static bool ovnet_valid_ipv4(struct sk_buff *skb)
{
	struct iphdr *iph;
	if (!pskb_may_pull(skb, skb_network_offset(skb) + sizeof(struct iphdr)))
		return false;
	iph = ip_hdr(skb);
	if (iph->version != 4 || iph->ihl < 5)
		return false;
	return pskb_may_pull(skb, skb_network_offset(skb) + iph->ihl * 4);
}

static bool ovnet_valid_ipv6(struct sk_buff *skb)
{
	unsigned int offset = skb_network_offset(skb), length;
	struct ipv6hdr *ip6h;
	if (offset > skb->len ||
	    !pskb_may_pull(skb, offset + sizeof(struct ipv6hdr)))
		return false;
	ip6h = ipv6_hdr(skb);
	if (ip6h->version != 6)
		return false;
	length = ntohs(ip6h->payload_len);
	/* This Ethernet/1500-MTU driver doesn't implement IPv6 jumbograms. */
	if (!length && skb->len - offset > sizeof(struct ipv6hdr))
		return false;
	return sizeof(struct ipv6hdr) + length <= skb->len - offset;
}

/* Keep a 128-bit peer update coherent for softirq-side readers. */
static void ovnet_peer_snapshot(struct ovnet_dev_private *private, u32 *ip4,
			       struct in6_addr *ip6)
{
	spin_lock_bh(&private->peer_lock);
	*ip4 = private->peer_ip;
	*ip6 = private->peer_ip6;
	spin_unlock_bh(&private->peer_lock);
}

static int ovnet_validate_peer_attrs(struct nlattr *data[])
{
	if (data && data[IFLA_OVNET_PEER6]) {
		struct in6_addr peer;
		if (nla_len(data[IFLA_OVNET_PEER6]) != sizeof(peer))
			return -EINVAL;
		memcpy(&peer, nla_data(data[IFLA_OVNET_PEER6]), sizeof(peer));
		if (ipv6_addr_is_multicast(&peer) || ipv6_addr_v4mapped(&peer) ||
		    (ipv6_addr_type(&peer) & IPV6_ADDR_LOOPBACK))
			return -EINVAL;
	}
	return 0;
}

static void ovnet_update_peers(struct ovnet_dev_private *private,
			       struct nlattr *data[])
{
	if (!data)
		return;
	spin_lock_bh(&private->peer_lock);
	if (data[IFLA_OVNET_PEER])
		private->peer_ip = nla_get_u32(data[IFLA_OVNET_PEER]);
	if (data[IFLA_OVNET_PEER6])
		memcpy(&private->peer_ip6, nla_data(data[IFLA_OVNET_PEER6]),
		       sizeof(private->peer_ip6));
	spin_unlock_bh(&private->peer_lock);
}

static int check_is_local_skb(struct sk_buff *skb, int dir, u32 peerip,
			     const struct in6_addr *peerip6)
{
	struct iphdr *iph = NULL;
	struct ipv6hdr *ipv6h = NULL;
	u32 mask = 0x00FFFFFF;
	/* struct udphdr *udph = NULL; */

	if (skb->protocol == htons(ETH_P_IP)) {
		if (!ovnet_valid_ipv4(skb))
			return 1;
		iph = ip_hdr(skb);
		if (!iph) {
			return 1;
		}
		if (dir) {
			if (((iph->daddr & mask) == (peerip & mask)) || (iph->daddr == 0xffffffff)) {
				return 1;
			}
		} else {
			if (((iph->saddr & mask) == (peerip & mask)) || (iph->saddr == 0) || (iph->daddr == 0xffffffff)) {
				return 1;
			}
		}
		return 0;
	} else if (skb->protocol == htons(ETH_P_IPV6)) {
		const struct in6_addr *addr;
		int type;
		/* An absent IPv6 peer leaves legacy IPv4-only RX behavior intact. */
		if (ipv6_addr_any(peerip6) || !ovnet_valid_ipv6(skb))
			return 1;
		ipv6h = ipv6_hdr(skb);
		if (ipv6_addr_is_multicast(&ipv6h->daddr))
			return 1;
		addr = dir ? &ipv6h->daddr : &ipv6h->saddr;
		type = ipv6_addr_type(addr);
		/* Preserve link-local discovery and the peer's local /64 traffic. */
		if (ipv6_addr_any(addr) || (type & (IPV6_ADDR_LINKLOCAL |
						 IPV6_ADDR_LOOPBACK)) ||
		    ipv6_prefix_equal(addr, peerip6, 64))
			return 1;
		return 0;
	} else {
		return 1;
	}
}


static unsigned int ovnet_dev_ingress_hook(void *priv, struct sk_buff *skb, const struct nf_hook_state *state)
{
	int ret = 0;
	int redirect_iif = 0;
	struct net_device *rediret_dev = NULL;
	struct ovnet_dev_private *private = NULL;
	u32 peer_ip;
	struct in6_addr peer_ip6;

	logi("cell_dev_ingress_hook enter!");
	if (!s_enable) {
		return NF_ACCEPT;
	}

	if (!skb->dev)
		return NF_ACCEPT;
	ret = get_ovnet_if_by_org(dev_net(skb->dev), skb->skb_iif, &redirect_iif);
	if (ret) {
		return NF_ACCEPT;
	}

	rcu_read_lock();
	rediret_dev = dev_get_by_index_rcu(dev_net(skb->dev), redirect_iif);
	if (!rediret_dev) {
		rcu_read_unlock();
		logi("cannot find redirect device for %u", redirect_iif);
		return NF_ACCEPT;
	}

	private = netdev_priv(rediret_dev);
	ovnet_peer_snapshot(private, &peer_ip, &peer_ip6);
	if (check_is_local_skb(skb, 0, peer_ip, &peer_ip6)) {
		logi("recv skb is local");
		rcu_read_unlock();
		return NF_ACCEPT;
	}

	dev_hold(rediret_dev);
	skb->dev = rediret_dev;
	skb->skb_iif = rediret_dev->ifindex;
	skb->dev->stats.rx_packets += 1;
	skb->dev->stats.rx_bytes += skb->len;
	rcu_read_unlock();
	ret = netif_receive_skb_core(skb);
	dev_put(rediret_dev);
	logi("netif_receive_skb_core return %d", ret);

	return NF_STOLEN;
}


static int ovnet_open(struct net_device *dev)
{
	logk("device open...");
	netif_tx_start_all_queues(dev);
	return 0;
}


static int ovnet_close(struct net_device *dev)
{
	logk("device close...");
	netif_tx_stop_all_queues(dev);
	return 0;
}


static netdev_tx_t ovnet_xmit(struct sk_buff *skb, struct net_device *dev)
{
	int ret = 0;
	struct ovnet_dev_private *private = netdev_priv(dev);
	struct net_device *org_dev = NULL;
	struct iphdr *iph = NULL;
	int is_local_ip = 0;
	u32 xmit_dst_ip = 0;
	u32 peer_ip;
	struct in6_addr peer_ip6, xmit_dst_ip6;
	bool ipv6 = skb->protocol == htons(ETH_P_IPV6);

	logi("ovnet_xmit start! %d", dev->ifindex);
	if ((!ipv6 && (skb->protocol != htons(ETH_P_IP) || !ovnet_valid_ipv4(skb))) ||
	    (ipv6 && !ovnet_valid_ipv6(skb))) {
		logi("ovnet_xmit start! protocol not support %d", skb->protocol);
		dev_kfree_skb(skb);
		dev->stats.tx_dropped++;
		return NETDEV_TX_OK;
	}
	ovnet_peer_snapshot(private, &peer_ip, &peer_ip6);
	if (ipv6 && (ipv6_addr_any(&peer_ip6) ||
	    (ipv6_addr_type(&ipv6_hdr(skb)->daddr) & IPV6_ADDR_LOOPBACK))) {
		dev_kfree_skb(skb);
		dev->stats.tx_dropped++;
		return NETDEV_TX_OK;
	}
	if (!ipv6)
		iph = ip_hdr(skb);

	org_dev = private->bind_dev;
	if (!org_dev) {
		dev_kfree_skb(skb);
		dev->stats.tx_dropped++;
		logi("cannot find out device! %d", dev->ifindex);
		return NETDEV_TX_OK;
	}

	is_local_ip = check_is_local_skb(skb, 1, peer_ip, &peer_ip6);
	if (is_local_ip) {
		logi("warn: local packet send to this device");
		if (ipv6)
			xmit_dst_ip6 = ipv6_hdr(skb)->daddr;
		else
			xmit_dst_ip = iph->daddr;
	} else {
		dev->stats.tx_packets += 1;
		dev->stats.tx_bytes += skb->len;
		if (ipv6)
			xmit_dst_ip6 = peer_ip6;
		else
			xmit_dst_ip = peer_ip;
	}

	skb->dev = org_dev;
	ret = ipv6 ? neigh_xmit(NEIGH_ND_TABLE, skb->dev, &xmit_dst_ip6, skb) :
		     neigh_xmit(NEIGH_ARP_TABLE, skb->dev, &xmit_dst_ip, skb);
	logi("ovnet_xmit return %d", ret);

	return NETDEV_TX_OK;
}


static int ovnet_validate_addr(struct net_device *dev)
{
	logk("ovnet_validate_addr ");
	return 0;
}


static int ovnet_init_dev(struct net_device *dev)
{
	logk("ovnet_init_dev ");
	return 0;
}


static const struct net_device_ops ovnet_netdev_ops = {
	.ndo_open = ovnet_open,
	.ndo_stop = ovnet_close,
	.ndo_start_xmit = ovnet_xmit,
	.ndo_validate_addr = ovnet_validate_addr,
	.ndo_init = ovnet_init_dev,
};


static int ovnet_register_dev(struct net_device *dev, u32 ifindex)
{
	struct net *net = dev_net(dev);
	struct ovnet_dev_private *private = netdev_priv(dev);
	struct net_device *bind_dev;
	int ret;
	if (!ifindex)
		return -EINVAL;
	rcu_read_lock();
	bind_dev = dev_get_by_index_rcu(net, ifindex);
	if (bind_dev)
		dev_hold(bind_dev);
	rcu_read_unlock();
	if (!bind_dev)
		return -ENODEV;
	/* Binding an ovnet to another ovnet permits cycles and recursive TX. */
	if (bind_dev->netdev_ops == &ovnet_netdev_ops) {
		dev_put(bind_dev);
		return -EINVAL;
	}
	private->nf_ops.dev = bind_dev;
	private->nf_ops.hook = ovnet_dev_ingress_hook;
	private->nf_ops.pf = NFPROTO_NETDEV;
	private->nf_ops.hooknum = NF_NETDEV_INGRESS;
	private->nf_ops.priority = NF_IP_PRI_FILTER + 1;
	/* Registration may sleep; the device reference outlives the RCU lookup. */
	ret = nf_register_net_hook(net, &private->nf_ops);
	if (ret) {
		memset(&private->nf_ops, 0, sizeof(private->nf_ops));
		dev_put(bind_dev);
		return ret;
	}
	private->bind_dev = bind_dev;
	return 0;
}

static int ovnet_unregister_dev(struct net_device *dev)
{
	struct ovnet_dev_private *private = netdev_priv(dev);
	if (private->bind_dev) {
		/* Unregistration synchronizes callbacks and must not hold RCU. */
		nf_unregister_net_hook(dev_net(dev), &private->nf_ops);
		memset(&private->nf_ops, 0, sizeof(private->nf_ops));
		dev_put(private->bind_dev);
		private->bind_dev = NULL;
	}
	return 0;
}

/* NETDEV_UNREGISTER runs under RTNL before netdev_wait_allrefs().
 * Release our reference and hook before a Wi-Fi/interface removal can wait
 * forever on a binding held by a surviving ovnet device.
 */
static int ovnet_netdev_event(struct notifier_block *nb, unsigned long event, void *ptr)
{
	struct net_device *under = netdev_notifier_info_to_dev(ptr), *dev;
	struct ovnet_dev_private *private;
	if (event != NETDEV_UNREGISTER || under->netdev_ops == &ovnet_netdev_ops)
		return NOTIFY_DONE;
	for_each_netdev(dev_net(under), dev) {
		if (dev->netdev_ops != &ovnet_netdev_ops)
			continue;
		private = netdev_priv(dev);
		if (private->bind_dev != under)
			continue;
		netif_tx_disable(dev);
		synchronize_net();
		del_if_map_by_ovnet(dev_net(dev), dev->ifindex);
		ovnet_unregister_dev(dev);
		private->bind_if = 0;
		if (netif_running(dev))
			netif_tx_start_all_queues(dev);
	}
	return NOTIFY_DONE;
}

static struct notifier_block ovnet_netdev_notifier = {
	.notifier_call = ovnet_netdev_event,
};

static void ovnet_dev_free(struct net_device *dev)
{
	logk("ovnet_dev_free %s...", dev->name);
	return;
}


#define OVNET_FEATURE (NETIF_F_HW_CSUM | NETIF_F_SG  | NETIF_F_FRAGLIST | \
						NETIF_F_TSO_ECN | NETIF_F_TSO | NETIF_F_TSO6      | \
						NETIF_F_GSO_ENCAP_ALL                             | \
						NETIF_F_HIGHDMA | NETIF_F_HW_VLAN_CTAG_TX         | \
						NETIF_F_HW_VLAN_STAG_TX)



static void ovnet_setup(struct net_device *dev)
{
	struct ovnet_dev_private *private = netdev_priv(dev);
	logk("ovnet_setup  %s..", dev->name);

	dev->netdev_ops = &ovnet_netdev_ops;
	ether_setup(dev);
	spin_lock_init(&private->peer_lock);
	dev->tx_queue_len = MAX_TXQUEUE_LEN;
	dev->features |= OVNET_FEATURE;
	dev->hw_features |= dev->features;
	dev->hw_enc_features |= dev->features;
	dev->vlan_features |= OVNET_FEATURE & ~(NETIF_F_HW_VLAN_CTAG_TX |
											NETIF_F_HW_VLAN_STAG_TX);
	dev->flags |= IFF_NOARP | IFF_POINTOPOINT;
	dev->priv_flags &= ~IFF_TX_SKB_SHARING;
	netif_keep_dst(dev);
	eth_hw_addr_random(dev);
	dev->needs_free_netdev = true;
	dev->priv_destructor = ovnet_dev_free;
}


static int ovnet_validate(struct nlattr *tb[], struct nlattr *data[], struct netlink_ext_ack *extack)
{
	logk("cell_validate %p %p %p", tb, data, extack);
	return ovnet_validate_peer_attrs(data);
}


/* Called under RTNL; writers cannot consume a slot between validation
 * and update. The spinlock also protects softirq-side readers.
 */
static int ovnet_map_can_bind(struct net *net, u32 org_if, u32 ovnet_if)
{
	int i, available = 0;
	spin_lock_bh(&s_if_lock);
	for (i = 0; i < VIRTUAL_NET_MAX; i++) {
		if (s_if_map[i].net == net && s_if_map[i].org_if == org_if &&
		    s_if_map[i].ovnet_if && s_if_map[i].ovnet_if != ovnet_if) {
			spin_unlock_bh(&s_if_lock);
			return -EBUSY;
		}
		if (!s_if_map[i].ovnet_if || (s_if_map[i].net == net &&
		    ovnet_if && s_if_map[i].ovnet_if == ovnet_if))
			available = 1;
	}
	spin_unlock_bh(&s_if_lock);
	return available ? 0 : -ENOSPC;
}

static int ovnet_newlink(struct net *src_net, struct net_device *dev,
	struct nlattr *tb[], struct nlattr *data[], struct netlink_ext_ack *extack)
{
	struct ovnet_dev_private *private = netdev_priv(dev);
	int ret;
	ret = ovnet_validate_peer_attrs(data);
	if (ret)
		return ret;
	ovnet_update_peers(private, data);
	if (data && data[IFLA_OVNET_BIND]) {
		private->bind_if = nla_get_u32(data[IFLA_OVNET_BIND]);
		if (private->bind_if) {
			ret = ovnet_map_can_bind(dev_net(dev), private->bind_if, 0);
			if (ret)
				return ret;
			/* Fail before registering a link; rtnetlink still owns its allocation. */
			ret = ovnet_register_dev(dev, private->bind_if);
			if (ret)
				return ret;
		}
	}
	ret = register_netdevice(dev);
	if (ret) {
		ovnet_unregister_dev(dev);
		return ret;
	}
	if (private->bind_if)
		update_ovnet_org_if(dev_net(dev), private->bind_if, dev->ifindex);
	return 0;
}

static int ovnet_changelink(struct net_device *dev, struct nlattr *tb[], struct nlattr *data[], struct netlink_ext_ack *extack)
{
	struct ovnet_dev_private *private = netdev_priv(dev);
	u32 old_if, bind_if;
	int ret;
	if (!data)
		return 0;
	ret = ovnet_validate_peer_attrs(data);
	if (ret)
		return ret;
	if (data[IFLA_OVNET_BIND]) {
		bind_if = nla_get_u32(data[IFLA_OVNET_BIND]);
		old_if = private->bind_if;
		if (bind_if != old_if) {
			/* RTNL keeps the target alive through validation/registration. */
			if (bind_if && !__dev_get_by_index(dev_net(dev), bind_if))
				return -ENODEV;
			if (bind_if == dev->ifindex)
				return -EINVAL;
			if (bind_if) {
				ret = ovnet_map_can_bind(dev_net(dev), bind_if, dev->ifindex);
				if (ret)
					return ret;
			}
			/* Quiesce TX before releasing the old device reference. */
			netif_tx_disable(dev);
			synchronize_net();
			ovnet_unregister_dev(dev);
			if (bind_if) {
				ret = ovnet_register_dev(dev, bind_if);
				if (ret) {
					/* Report failure and retain the old binding if possible. */
					if (old_if && ovnet_register_dev(dev, old_if)) {
						private->bind_if = 0;
						del_if_map_by_ovnet(dev_net(dev), dev->ifindex);
					}
					if (netif_running(dev))
						netif_tx_start_all_queues(dev);
					return ret;
				}
				update_ovnet_org_if(dev_net(dev), bind_if, dev->ifindex);
			} else {
				del_if_map_by_ovnet(dev_net(dev), dev->ifindex);
			}
			private->bind_if = bind_if;
			if (netif_running(dev))
				netif_tx_start_all_queues(dev);
		}
	}
	ovnet_update_peers(private, data);
	return 0;
}

static void ovnet_dellink(struct net_device *dev, struct list_head *head)
{
	logk("ovnet_dellink ....%s", dev->name);
	netif_tx_disable(dev);
	synchronize_net();
	del_if_map_by_ovnet(dev_net(dev), dev->ifindex);
	ovnet_unregister_dev(dev);
	unregister_netdevice_queue(dev, head);
	return;
}


static size_t ovnet_get_size(const struct net_device *dev)
{
	return nla_total_size(sizeof(u32)) + nla_total_size(sizeof(u32)) +
	       nla_total_size(sizeof(struct in6_addr));
}

static int ovnet_fillinfo(struct sk_buff *skb, const struct net_device *dev)
{
	struct ovnet_dev_private *private = netdev_priv(dev);
	u32 peer_ip;
	struct in6_addr peer_ip6;
	ovnet_peer_snapshot(private, &peer_ip, &peer_ip6);

	if (nla_put_u32(skb, IFLA_OVNET_BIND, private->bind_if)) {
		goto nla_put_failure;
	}
	if (nla_put_u32(skb, IFLA_OVNET_PEER, peer_ip)) {
		goto nla_put_failure;
	}
	if (nla_put(skb, IFLA_OVNET_PEER6, sizeof(peer_ip6), &peer_ip6))
		goto nla_put_failure;
	return 0;
nla_put_failure:
	return -EMSGSIZE;
}


static const struct nla_policy ovnet_nl_policy[IFLA_OVNET_MAX + 1] = {
	[IFLA_OVNET_BIND] = { .type = NLA_U32 },
	[IFLA_OVNET_PEER] = { .type = NLA_U32 },
	[IFLA_OVNET_PEER6] = { .type = NLA_BINARY, .len = sizeof(struct in6_addr) },
};


static struct rtnl_link_ops ovnet_link_ops __read_mostly = {
	.kind			= "ovnet",
	.priv_size		= sizeof(struct ovnet_dev_private),
	.setup			= ovnet_setup,
	.validate		= ovnet_validate,
	.newlink		= ovnet_newlink,
	.changelink		= ovnet_changelink,
	.dellink		= ovnet_dellink,
	.get_size		= ovnet_get_size,
	.maxtype		= IFLA_OVNET_MAX,
	.policy			= ovnet_nl_policy,
	.fill_info		= ovnet_fillinfo,
};



static struct ctl_table s_ovnet_dev_sysctl_table[] __read_mostly = {
	{
		.procname = "debug",
		.data = &s_debug,
		.maxlen = sizeof(int),
		.mode = 0644,
		.proc_handler = proc_dointvec,
	},
	{
		.procname = "enable",
		.data = &s_enable,
		.maxlen = sizeof(int),
		.mode = 0644,
		.proc_handler = proc_dointvec,
	},
	{}
};

static struct ctl_table_header * s_ovnet_table_header = NULL;


static int numvnets = 3;
module_param(numvnets, int, 0);
MODULE_PARM_DESC(numvnets, "Number of ovnet devices");


static int init_dev_one(int index)
{
	struct net_device *dev_vnet;
	int err;

	dev_vnet = alloc_netdev(sizeof(struct ovnet_dev_private), "ovnet%d", NET_NAME_UNKNOWN, ovnet_setup);

	if (!dev_vnet)
		return -ENOMEM;

	dev_vnet->rtnl_link_ops = &ovnet_link_ops;
	err = register_netdevice(dev_vnet);
	if (err < 0)
		goto err;

	return 0;

err:
	free_netdev(dev_vnet);
	return err;
}

static int init_ovnet_dev_all(void)
{
	int err = 0;
	int i = 0;

	for (i = 0; i < numvnets && !err; i++) {
		err = init_dev_one(i);
		cond_resched();
	}

	return err;
}


static int __init ovnet_dev_init(void)
{
	int ret = 0;

	logk("ovnet_dev_init...");
	spin_lock_init(&s_if_lock);
	memset((char *)s_if_map, 0, sizeof(s_if_map));
	ret = register_netdevice_notifier(&ovnet_netdev_notifier);
	if (ret)
		return ret;

	rtnl_lock();
	ret = __rtnl_link_register(&ovnet_link_ops);
	if (ret) {
		rtnl_unlock();
		unregister_netdevice_notifier(&ovnet_netdev_notifier);
		logk("rtnl_link_register failed! %d", ret);
		return -1;
	}
	ret = init_ovnet_dev_all();
	if (ret) {
		__rtnl_link_unregister(&ovnet_link_ops);
		rtnl_unlock();
		unregister_netdevice_notifier(&ovnet_netdev_notifier);
		logk("init default ovnet device failed! %d", ret);
		return -1;
	}
	rtnl_unlock();

	s_ovnet_table_header = register_net_sysctl(&init_net, "net/ovnet_dev", s_ovnet_dev_sysctl_table);

	return 0;
}


static void __exit ovnet_dev_fini(void)
{
	/* TODO: del all devices */

	rtnl_link_unregister(&ovnet_link_ops);
	unregister_netdevice_notifier(&ovnet_netdev_notifier);

	if (s_ovnet_table_header) {
		unregister_net_sysctl_table(s_ovnet_table_header);
	}

	logk("ovnet_dev_fini...");
}

module_init(ovnet_dev_init);
module_exit(ovnet_dev_fini);
#endif
MODULE_LICENSE("GPL");
MODULE_ALIAS_RTNL_LINK("ovnet");



