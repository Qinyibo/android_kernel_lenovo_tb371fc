from pathlib import Path
import ast,json,subprocess
B=Path(__file__).resolve().parent.parent;O=B/'irq-wake-owner-v43'
ns={};exec('import re',ns)
tree=ast.parse((B/'test_touch_order_v36.py').read_text(encoding='utf-8'))
for n in tree.body:
    if isinstance(n,ast.FunctionDef) and n.name=='function':
        source=ast.get_source_segment((B/'test_touch_order_v36.py').read_text(encoding='utf-8'),n)
        source=source.replace('(?:int|void)',r'(?:int|void|int32_t|ssize_t)')
        exec(source,ns)
extract=ns['function']
dsi=(O/'overlays/dsi_display.c').read_text(encoding='utf-8')
ext=(O/'overlays/nt36xxx_ext_proc.c').read_text(encoding='utf-8')
common=r'''
#define _GNU_SOURCE
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <errno.h>
#include <limits.h>
#include <sys/types.h>
#define ARRAY_SIZE(x) (sizeof(x)/sizeof((x)[0]))
#define ERESTARTSYS 512
#define NVT_TOUCH_ESD_PROTECT 0
#define NVT_LOG(...) ((void)0)
#define NVT_ERR(...) ((void)0)
#define DSI_ERR(...) ((void)0)
#define DSI_INFO(...) ((void)0)
#define DRM_PANEL_BLANK_UNBLANK 0
#define DRM_PANEL_EVENT_TOUCH_ABORT 11
#define DRM_PANEL_EVENT_TOUCH_ARM 12
#define DSI_OP_VIDEO_MODE 1
#define DSI_OP_CMD_MODE 2
#define DSI_MODE_FLAG_POMS 4
#define DSI_ALL_CLKS 7
#define DSI_CLK_OFF 0
#define EVENT_MAP_RESET_COMPLETE 0x60
typedef uint32_t u32;
struct drm_panel_notifier {void *data; u32 id;};
struct mode {int dsi_mode_flags;};
struct panel {int drm_panel;struct mode *cur_mode;};
struct dsi_display {struct panel *panel;struct {int panel_mode;} config;int display_lock;void *dsi_clk_handle;u32 r94_touch_resume_id;bool r94_touch_engine_started,r94_touch_panel_started,r94_touch_resume_cancelled;};
static int locks,arm_error,abort_error,post_error,arm_calls,abort_calls,engine_off,panel_off,clock_off;
static bool sde_live;
static u32 aborted_id;
static void mutex_lock(int *m){(void)m;assert(!locks);locks++;}
static void mutex_unlock(int *m){(void)m;assert(locks==1);locks--;}
static int mutex_lock_interruptible(int *m){mutex_lock(m);return 0;}
static int notifier_to_errno(int r){return r;}
static int drm_panel_notifier_call_chain(int *p,int ev,struct drm_panel_notifier *n){(void)p;assert(!locks);if(ev==DRM_PANEL_EVENT_TOUCH_ABORT){abort_calls++;aborted_id=n->id;return abort_error;}assert(ev==DRM_PANEL_EVENT_TOUCH_ARM);arm_calls++;return arm_error;}
static int dsi_display_vid_engine_disable(struct dsi_display *d){(void)d;assert(locks&&!sde_live);engine_off++;return 0;}
static int dsi_display_cmd_engine_disable(struct dsi_display *d){return dsi_display_vid_engine_disable(d);}
static int dsi_panel_disable(struct panel *p){(void)p;assert(locks&&!sde_live);panel_off++;return 0;}
static int dsi_panel_post_enable(struct panel *p){(void)p;assert(locks);return post_error;}
static void dsi_panel_mode_switch_to_cmd(struct panel *p){(void)p;assert(locks);}
static void dsi_panel_mode_switch_to_vid(struct panel *p){(void)p;assert(locks);}
static int dsi_display_clk_ctrl(void *h,int clks,int state){(void)h;assert(clks==DSI_ALL_CLKS&&state==DSI_CLK_OFF);clock_off++;return 0;}
struct seq_file {char text[64];};
struct mapping {int EVENT_BUF_ADDR;};
struct ts_data {int lock;void *client;struct mapping *mmap;struct {uint8_t degree,direction;uint16_t y1,y2;} edge_grid_zone_info;};
static struct mapping map;
static struct ts_data touch={.mmap=&map},*ts=&touch;
static bool bTouchIsAwake=true;
static int page_error,spi_error,page_calls,spi_calls,set_calls,copy_fault;
static int nvt_set_page(int addr){(void)addr;assert(locks);page_calls++;return page_error;}
static int CTP_SPI_READ(void *c,uint8_t *b,int size){(void)c;assert(locks&&size==6);spi_calls++;b[1]=0xA3;return spi_error;}
static void seq_printf(struct seq_file *m,const char *fmt,unsigned int value){snprintf(m->text,sizeof(m->text),fmt,value);}
static unsigned long copy_from_user(void *to,const void *from,size_t n){if(copy_fault)return n;memcpy(to,from,n);return 0;}
static char *strim(char *p){char *e=p+strlen(p);while(e>p&&isspace((unsigned char)e[-1]))*--e=0;while(isspace((unsigned char)*p))p++;return p;}
static int kstrtouint(const char *p,int base,unsigned int *v){char *end;if(!*p||*p=='-')return -EINVAL;errno=0;unsigned long n=strtoul(p,&end,base);if(errno==ERANGE||n>UINT_MAX)return -ERANGE;if(end==p||*end)return -EINVAL;*v=(unsigned int)n;return 0;}
struct file {int unused;};
static int nvt_edge_grid_zone_set(uint8_t d,uint8_t r,uint16_t y1,uint16_t y2){assert(d<=4&&r<=2&&y1<=y2);set_calls++;return 0;}
'''
real='\n'.join(extract(dsi,n) for n in ['r94_dsi_touch_abort_only','r94_dsi_touch_pre_enable_rollback','r94_dsi_touch_arm','dsi_display_post_enable_r94_locked'])
real+='\n'+extract(ext,'nvt_fw_status_show')+'\n'+extract(ext,'nvt_edge_grid_zone_store')
# Preserve the exact one-argument seq_printf call as well as the formatted call.
common=common.replace('static void seq_printf(struct seq_file *m,const char *fmt,unsigned int value){snprintf(m->text,sizeof(m->text),fmt,value);}',r'''#include <stdarg.h>
static void seq_printf(struct seq_file *m,const char *fmt,...){va_list a;va_start(a,fmt);vsnprintf(m->text,sizeof(m->text),fmt,a);va_end(a);}''')
tests=r'''
static struct mode mode;
static struct panel panel={.cur_mode=&mode};
static struct dsi_display d;
static void init(void){memset(&d,0,sizeof(d));d.panel=&panel;d.config.panel_mode=DSI_OP_VIDEO_MODE;d.r94_touch_resume_id=9;d.r94_touch_engine_started=d.r94_touch_panel_started=true;mode.dsi_mode_flags=0;locks=arm_error=abort_error=post_error=arm_calls=abort_calls=engine_off=panel_off=clock_off=0;sde_live=true;aborted_id=0;}
static int status(void){struct seq_file s={{0}};int r=nvt_fw_status_show(&s,NULL);assert(!locks);if(r<0)assert(!s.text[0]);else if(bTouchIsAwake)assert(!strcmp(s.text,"A3\n"));else assert(!strcmp(s.text,"A0\n"));return r;}
static void invalid(const char *p,size_t n){unsigned char before[sizeof(touch.edge_grid_zone_info)];memcpy(before,&touch.edge_grid_zone_info,sizeof(before));int calls=set_calls;assert(nvt_edge_grid_zone_store(NULL,p,n,NULL)<0);assert(!memcmp(before,&touch.edge_grid_zone_info,sizeof(before)));assert(calls==set_calls);}
int main(void){
 init();post_error=-EIO;assert(dsi_display_post_enable_r94_locked(&d)==-EIO);assert(abort_calls==1&&aborted_id==9&&!arm_calls&&!d.r94_touch_resume_id&&d.r94_touch_resume_cancelled&&!engine_off&&!panel_off);puts("PASS active_SDE_panel_post_failure_aborts_transaction_without_poweroff");
 init();arm_error=-ETIMEDOUT;abort_error=-EIO;assert(dsi_display_post_enable_r94_locked(&d)==-ETIMEDOUT);assert(arm_calls==1&&abort_calls==1&&!d.r94_touch_resume_id&&d.r94_touch_resume_cancelled&&!engine_off&&!panel_off);puts("PASS ARM_failure_preserves_original_error_even_if_ABORT_fails_and_clears_id");
 init();assert(!dsi_display_post_enable_r94_locked(&d));assert(arm_calls==1&&!abort_calls&&!d.r94_touch_resume_id&&!d.r94_touch_resume_cancelled&&!engine_off&&!panel_off);puts("PASS normal_post_enable_ARMs_once_without_hardware_rollback");
 init();d.r94_touch_resume_id=0;d.r94_touch_resume_cancelled=true;assert(dsi_display_post_enable_r94_locked(&d)==-ECANCELED);assert(!arm_calls&&!abort_calls&&!engine_off&&!panel_off);puts("PASS cancelled_post_enable_cannot_rearm_old_transaction");
 init();sde_live=false;r94_dsi_touch_pre_enable_rollback(&d);assert(engine_off==1&&panel_off==1&&abort_calls==1&&!d.r94_touch_resume_id);puts("PASS pre_enable_rollback_retains_owned_engine_and_panel_cleanup");
 init();sde_live=false;d.config.panel_mode=DSI_OP_CMD_MODE;d.r94_touch_panel_started=false;r94_dsi_touch_pre_enable_rollback(&d);assert(engine_off==1&&!panel_off&&!d.r94_touch_resume_id);puts("PASS command_mode_partial_pre_enable_rollback_only_owned_hardware");
 init();d.r94_touch_resume_id=0;assert(!r94_dsi_touch_abort_only(&d));assert(!abort_calls&&!engine_off&&!panel_off&&d.r94_touch_resume_cancelled);puts("PASS abort_without_id_is_idempotent_and_never_powers_down");
 locks=0;bTouchIsAwake=true;page_error=-EIO;spi_error=page_calls=spi_calls=0;assert(status()==-EIO&&page_calls==1&&!spi_calls);puts("PASS page_error_never_reads_or_publishes_status");
 page_error=0;spi_error=-ETIMEDOUT;assert(status()==-ETIMEDOUT&&spi_calls==1);puts("PASS SPI_error_cannot_publish_buffer_modified_to_A3");
 spi_error=0;assert(!status());puts("PASS successful_hardware_status_preserved");
 bTouchIsAwake=false;int calls=spi_calls;assert(!status()&&spi_calls==calls);puts("PASS sleeping_status_never_accesses_SPI");
 const char *good="4,2,65535,65535\n";assert(nvt_edge_grid_zone_store(NULL,good,strlen(good),NULL)==(ssize_t)strlen(good));assert(touch.edge_grid_zone_info.y2==65535&&set_calls==1);puts("PASS full_uint16_grid_coordinates_with_newline_fit_bounded_buffer");
 const char terminated[]="1,1,100,200";assert(nvt_edge_grid_zone_store(NULL,terminated,sizeof(terminated),NULL)==sizeof(terminated));const char newline_zero[]="1,1,100,200\n";assert(nvt_edge_grid_zone_store(NULL,newline_zero,sizeof(newline_zero),NULL)==sizeof(newline_zero));invalid("\0",1);const char two_zero[]="1,1,100,200\0";invalid(two_zero,sizeof(two_zero));puts("PASS legacy_terminal_NUL_and_newline_NUL_allowed_empty_or_multiple_NUL_rejected");
 invalid("1,2,3",5);invalid("1,2,3,4,5",9);invalid("1,2,3,4junk",11);invalid("1,-1,3,4",8);invalid("5,2,3,4",7);invalid("1,3,3,4",7);invalid("1,2,5,4",7);invalid("1,2,65536,65536",15);invalid("1,2,4294967296,4",16);invalid("1,2,3,4\0junk",12);puts("PASS malformed_missing_extra_negative_overflow_hidden_payload_leave_state_unchanged");
 char large[256];memset(large,'1',sizeof(large));invalid(large,sizeof(large));invalid("",0);copy_fault=1;invalid(good,strlen(good));assert(!locks);puts("PASS oversized_empty_and_copy_fault_never_write_state_or_hardware");
 return 0;
}
'''
p=O/'failure-cases.c';p.write_text(common+real+tests,encoding='utf-8')
wp='/mnt/c/'+str(p).replace('\\','/').split(':/',1)[1]
r=subprocess.run(['wsl','-d','TB371FC-Builder','-u','root','--exec','/usr/bin/gcc','-std=gnu11','-Wall','-Wextra','-Wno-unused-parameter','-Wno-sign-compare','-fsanitize=address,undefined','-g',wp,'-o',wp+'.test'],capture_output=True,timeout=45)
(O/'failure-cases-compile.txt').write_bytes(r.stdout+r.stderr);assert not r.returncode,(r.stdout+r.stderr).decode()
r=subprocess.run(['wsl','-d','TB371FC-Builder','-u','root','--exec',wp+'.test'],capture_output=True,timeout=30)
(O/'failure-cases-run.txt').write_bytes(r.stdout+r.stderr);assert not r.returncode,(r.stdout+r.stderr).decode()
assert r.stdout.count(b'PASS ')==15
result={'state':'15_EXTRACTED_REAL_FUNCTION_FAILURE_AND_USER_INPUT_CASES_PASS','sanitizers':['address','undefined'],'hardware_and_notifiers_substituted':True,'physical_acceptance':False,'black_screen_root_cause_confirmed':False}
(O/'failure-tests-result.json').write_text(json.dumps(result,indent=2)+'\n');print(r.stdout.decode())
