"""Exercise extracted production functions; no device or regulator access."""
from pathlib import Path
import subprocess,sys
W=Path(__file__).resolve().parent
if len(sys.argv)==3:
    source=Path(sys.argv[1]).resolve();W=Path(sys.argv[2]).resolve()
    W.mkdir(parents=True,exist_ok=False)
    base='9dd8f4f9edee33052c4c52706131fe72e43f2ef5'
    for name in ['dsi_panel.c','sde_connector.c','sde_connector.h','dsi_drm.c']:
        relative='techpack/display/msm/'+('sde/' if name.startswith('sde_') else 'dsi/')+name
        original=subprocess.check_output(['git','-C',str(source),'show',base+':'+relative])
        (W/name).write_bytes(original)
        (W/(name+'.candidate')).write_bytes((source/relative).read_bytes())
elif len(sys.argv)!=1:
    raise SystemExit('Usage: prepare_tests.py [kernel_checkout new_output_directory]')

def function(text,name):
    at=text.index(name+'(')
    start=text.rfind('\n',0,at)+1
    opening=text.index('{',at);level=1;pos=opening+1
    while level:
        if text[pos]=='{':level+=1
        if text[pos]=='}':level-=1
        pos+=1
    return text[start:pos]+'\n'

stub=r'''
#include <assert.h>
#include <errno.h>
#include <pthread.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint8_t u8;
typedef uint32_t u32;
typedef int irqreturn_t;
#define IRQ_HANDLED 1
#define DRM_MODE_CONNECTOR_DSI 14
#define SDE_MODE_DPMS_ON 0
#define SDE_MODE_DPMS_LP1 1
#define atomic_read(p) (*(p))
#define atomic_set(p,v) (*(p)=(v))
#define DSI_INFO(...) ((void)0)
#define DSI_ERR(...) ((void)0)
#define DSI_WARN(...) ((void)0)
#define SDE_ERROR(...) ((void)0)
#define SDE_EVT32(...) ((void)0)
#define SDE_EVTLOG_ERROR 0
#define READ_ONCE(x) (x)
#define pr_err_once(...) ((void)0)
#define DRM_EVENT_PANEL_DEAD 1
#define BL_UPDATE_DELAY_UNTIL_FIRST_FRAME 1
#define MSM_ENC_TX_COMPLETE 1
#define FB_BLANK_UNBLANK 0
#define BL_CORE_FBBLANK 1
#define DSI_MODE_FLAG_DMS 1
#define DSI_MODE_FLAG_DMS_FPS 2
struct panel {
    pthread_mutex_t panel_lock;
    struct {bool panel_dead_flag,is_tddi_flag,tddi_doubleclick_flag,pending_lhbm_state;int esd_err_irq_gpio;
            uint64_t panel_id;} mi_cfg;
    struct {int tp_reset_gpio,disp_en_gpio,reset_gpio,lcd_mode_sel_gpio;
            int reset_powerdown_delay;} reset_config;
    struct {int en_gpio,bl_update;} bl_config;
    struct {int dsi_mode_flags;} *cur_mode;
    int power_info,panel_test_gpio,esd_recovery_pending,power_mode;
    struct {bool cphy_strength;} host_config;
    bool reset_gpio_always_on,lp11_init,panel_initialized;
    const char *name;
};
#define dsi_panel panel
struct dsi_display {struct panel *panel;const char *display_type;};
struct drm_connector {struct {int id;} base;void *dev;};
struct encoder {struct {int id;} base;};
struct backlight {struct {int power,state,brightness;} props;};
struct sde_connector {
    struct drm_connector base;
    struct dsi_display *display;
    struct encoder *encoder;
    u32 panel_dead_seq,panel_recovery_seq;
    int connector_type;
    bool panel_dead,allow_bl_update;
    struct backlight *bl_device;
};
#define to_sde_connector(p) ((struct sde_connector *)(p))
struct drm_event {int type,length;};
static int on_calls,off_calls,fail_power,fail_pinctrl,fail_reset;
static int notifications,failures,checks,events_with_false_payload;
static struct panel *current_panel;
static void (*notify_hook)(void),(*backlight_hook)(void);
static int dsi_pwr_enable_regulator(int *info,bool on)
{(void)info;if(on){on_calls++;return fail_power?-EIO:0;}off_calls++;return 0;}
static int gpio_is_valid(int gpio){return gpio>=0;}
static int gpio_get_value(int gpio){(void)gpio;return 0;}
static void gpio_set_value(int gpio,int value){(void)gpio;(void)value;}
static int gpio_direction_output(int gpio,int value){(void)gpio;(void)value;return 0;}
static int gpio_direction_input(int gpio){(void)gpio;return 0;}
static void mdelay(int n){(void)n;}
static void usleep_range(int a,int b){(void)a;(void)b;}
static int dsi_panel_set_pinctrl_state(struct panel *p,bool on)
{(void)p;return on&&fail_pinctrl?-EIO:0;}
static int dsi_panel_reset(struct panel *p){(void)p;return fail_reset?-EIO:0;}
static void dsi_panel_acquire_panel_lock(struct panel *p){assert(!pthread_mutex_lock(&p->panel_lock));}
static void dsi_panel_release_panel_lock(struct panel *p){assert(!pthread_mutex_unlock(&p->panel_lock));}
static bool dsi_panel_initialized(struct panel *p){return p->panel_initialized;}
static void dsi_panel_esd_irq_ctrl_locked(struct panel *p,bool enabled){(void)p;(void)enabled;}
static void sde_encoder_display_failure_notification(struct encoder *e,bool skip){(void)e;(void)skip;}
static int sde_encoder_wait_for_event(struct encoder *e,int event){(void)e;(void)event;return 0;}
static void mi_disp_set_fod_queue_work(int a,bool b){(void)a;(void)b;}
static void backlight_update_status(struct backlight *b){(void)b;if(backlight_hook)backlight_hook();}
static void msm_mode_object_event_notify(void *a,void *b,struct drm_event *e,u8 *payload)
{
    (void)a;(void)b;assert(e->length==(int)sizeof(bool));
    /* External notification must run after releasing panel_lock. */
    assert(!pthread_mutex_trylock(&current_panel->panel_lock));
    assert(!pthread_mutex_unlock(&current_panel->panel_lock));
    if(notify_hook)notify_hook();
    notifications++;if(!*(bool *)payload)events_with_false_payload++;
}
'''

tests=r'''
static struct panel p;
static struct dsi_display display;
static struct sde_connector conn;
static struct encoder encoder;
static void fresh(void)
{
    static bool initialized;
    if(initialized)assert(!pthread_mutex_destroy(&p.panel_lock));
    memset(&p,0,sizeof(p));memset(&display,0,sizeof(display));memset(&conn,0,sizeof(conn));
    assert(!pthread_mutex_init(&p.panel_lock,0));initialized=true;current_panel=&p;
    p.mi_cfg.is_tddi_flag=true;p.mi_cfg.tddi_doubleclick_flag=true;
    p.reset_config.tp_reset_gpio=p.reset_config.disp_en_gpio=p.reset_config.reset_gpio=-1;
    p.reset_config.lcd_mode_sel_gpio=p.panel_test_gpio=p.bl_config.en_gpio=-1;
    p.name="test";p.panel_initialized=true;display.panel=&p;display.display_type="primary";
    conn.display=&display;conn.encoder=&encoder;conn.connector_type=DRM_MODE_CONNECTOR_DSI;
    on_calls=off_calls=fail_power=fail_pinctrl=fail_reset=notifications=events_with_false_payload=0;
    notify_hook=backlight_hook=0;
}
#define CHECK(x,label) do {checks++;if(!(x)){fprintf(stderr,"FAIL %s\n",label);failures++;}}while(0)
static bool fault(bool request_power)
{
#ifdef CANDIDATE
    return _sde_connector_notify_panel_dead(&conn,request_power);
#else
    (void)request_power;return _sde_connector_notify_panel_dead(&conn);
#endif
}
static void begin(void)
{
#ifdef CANDIDATE
    sde_connector_helper_bridge_pre_enable(&conn.base);
#endif
}
static int power_on(void)
{int rc;dsi_panel_acquire_panel_lock(&p);rc=dsi_panel_power_on(&p);dsi_panel_release_panel_lock(&p);return rc;}
static void power_off(void)
{dsi_panel_acquire_panel_lock(&p);dsi_panel_power_off(&p);dsi_panel_release_panel_lock(&p);}
static void success(void){sde_connector_helper_bridge_enable(&conn.base);}
static void clear_during_notify(void){notify_hook=0;begin();success();}
static void *report_thread(void *arg){(void)arg;fault(true);return 0;}
static void fault_during_backlight(void)
{pthread_t thread;backlight_hook=0;assert(!pthread_create(&thread,0,report_thread,0));assert(!pthread_join(thread,0));}
int main(void)
{
    fresh();begin();CHECK(!power_on(),"healthy power_on");success();power_off();
    CHECK(on_calls==0&&off_calls==0,"ordinary gesture rails unchanged");
    CHECK(!conn.panel_dead&&!p.mi_cfg.panel_dead_flag,"healthy flags clear");

    fresh();CHECK(fault(true),"first failure reports");power_off();
    CHECK(off_calls==1&&p.mi_cfg.panel_dead_flag,"initial recovery OFF retains eligibility");
    begin();CHECK(!power_on(),"recovery ON");
    CHECK(p.mi_cfg.panel_dead_flag,"power_on must not consume recovery eligibility");
    /* Firmware PREPARE fails: native bridge skips success and unprepares. */
    power_off();CHECK(off_calls==2,"failed PREPARE rollback powers down");
    sde_connector_report_enable_failure(&conn.base);
    CHECK(notifications==1,"sticky notification stays coalesced");
    CHECK(conn.panel_dead&&p.mi_cfg.panel_dead_flag,"failure retains both dead flags");
    begin();power_on();CHECK(on_calls==2,"next recovery can power_on again");
    success();CHECK(!conn.panel_dead&&!p.mi_cfg.panel_dead_flag,"successful recovery clears both flags");
    int before=off_calls;power_off();CHECK(off_calls==before,"success restores normal keep-power policy");

    for(int mode=0;mode<3;mode++){
        fresh();fault(true);begin();
        if(mode==0)fail_power=1;if(mode==1)fail_pinctrl=1;if(mode==2)fail_reset=1;
        CHECK(power_on()==-EIO,"power/pinctrl/reset failure is propagated");
        CHECK(p.mi_cfg.panel_dead_flag,"early failure keeps recovery armed");
    }

    fresh();fault(true);begin();power_on();
    /* post_enable fails too: helper_bridge_enable must not be called. */
    power_off();CHECK(off_calls==1,"post_enable failure rollback still powers down");

    fresh();fault(true);begin();power_on();fault(true);success();
    CHECK(conn.panel_dead&&p.mi_cfg.panel_dead_flag,"late fault is not cleared by old success");
    CHECK(notifications==1,"late fault does not add automatic renotification");
    begin();success();CHECK(!conn.panel_dead&&!p.mi_cfg.panel_dead_flag,"next successful epoch can clear");

    fresh();notify_hook=clear_during_notify;fault(true);
    CHECK(events_with_false_payload==0,"notification carries stable true payload");

    fresh();fault(true);begin();power_on();
    struct backlight bl={.props={.brightness=1}};conn.bl_device=&bl;
    struct {int dsi_mode_flags;} mode={0};p.cur_mode=(void *)&mode;
    backlight_hook=fault_during_backlight;success();
    CHECK(conn.panel_dead&&p.mi_cfg.panel_dead_flag,"concurrent ESD before completion retained");

    fresh();fault(true);begin();power_on();
    esd_err_irq_handle(1,&conn);success();
    CHECK(conn.panel_dead&&p.mi_cfg.panel_dead_flag,"sticky ESD IRQ is counted before early return");
    fresh();fault(true);begin();power_on();p.esd_recovery_pending=1;
    esd_err_irq_handle(1,&conn);success();
    CHECK(conn.panel_dead&&p.mi_cfg.panel_dead_flag,"pending ESD IRQ is counted before early return");
    fresh();fault(true);begin();power_on();success();fault(true);
    CHECK(conn.panel_dead&&p.mi_cfg.panel_dead_flag&&notifications==2,"fault after completion reports and owns dead");
    fresh();begin();p.panel_initialized=false;esd_err_irq_handle(1,&conn);success();
    CHECK(!conn.panel_dead&&!p.mi_cfg.panel_dead_flag,"uninitialized-panel IRQ does not invent a fault");

#ifdef CANDIDATE
    fresh();CHECK(fault(false),"OFF/LP reports");
    CHECK(conn.panel_dead&&!p.mi_cfg.panel_dead_flag,"OFF/LP does not request rail recovery");
    begin();power_on();success();power_off();
    CHECK(on_calls==0&&off_calls==0,"OFF/LP original power policy retained");
    fresh();p.power_mode=2;esd_err_irq_handle(1,&conn);
    CHECK(conn.panel_dead&&!p.mi_cfg.panel_dead_flag,"actual OFF IRQ preserves notify-only policy");
    fresh();begin();pthread_t a,b;
    assert(!pthread_create(&a,0,report_thread,0));assert(!pthread_create(&b,0,report_thread,0));
    assert(!pthread_join(a,0));assert(!pthread_join(b,0));
    CHECK(notifications==1&&conn.panel_dead_seq==2,"simultaneous faults serialize and coalesce");
    success();CHECK(conn.panel_dead&&p.mi_cfg.panel_dead_flag,"faults after epoch snapshot survive");
#endif
    printf("%d checks; %d failures\n",checks,failures);
    return failures?1:0;
}
'''

for kind in ['before','candidate']:
    suffix='' if kind=='before' else '.candidate'
    panel=(W/('dsi_panel.c'+suffix)).read_text(encoding='utf-8')
    conn=(W/('sde_connector.c'+suffix)).read_text(encoding='utf-8')
    functions=[function(panel,'dsi_panel_power_on'),function(panel,'dsi_panel_power_off')]
    if kind=='candidate':functions.append(function(conn,'sde_connector_helper_bridge_pre_enable'))
    functions.extend(function(conn,name) for name in ['sde_connector_helper_bridge_enable','_sde_connector_notify_panel_dead','_sde_connector_report_panel_dead','sde_connector_report_enable_failure','esd_err_irq_handle'])
    # The ordinary keep-power policy is the real constant from this source.
    assert 'static bool p108_keep_panel_power = true;' in panel
    generated=stub+'\nstatic bool p108_keep_panel_power = true;\n'+'\n'.join(functions)+tests
    (W/('contract-'+kind+'.c')).write_bytes(generated.encode())
print('Extracted original and candidate functions for contract tests.')
