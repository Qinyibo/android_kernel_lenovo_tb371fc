"""Exercise the actual connector/KMS completion code with a simulated notifier."""
from pathlib import Path
import ast
import re
import subprocess

import sys
assert len(sys.argv) in (3, 4), 'Usage: prepare_tests.py kernel_checkout new_output [bare_git_directory]'
source = Path(sys.argv[1]).resolve()
W = Path(sys.argv[2]).resolve()
W.mkdir(parents=True, exist_ok=False)
GIT = ['git', '--git-dir='+sys.argv[3]] if len(sys.argv)==4 else ['git', '-C', str(source)]
BASE = '62d357f5e57f48d974873741f204c2fce1bf6c29'

def blob(path):
    return subprocess.check_output(GIT+['show', BASE+':'+path])

for name in ['sde_connector.c','sde_kms.c']:
    relative = 'techpack/display/msm/sde/'+name
    for kind, raw in [('before',blob(relative)),('candidate',(source/relative).read_bytes())]:
        target = W/kind/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(raw)



def function(text, name):
    match = re.search(r'^(?:static\s+)?(?:inline\s+)?(?:void|int|bool|irqreturn_t)\s+'
                      +re.escape(name)+r'\(', text, re.MULTILINE)
    assert match, name
    at = text.index(name+'(', match.start())
    start = text.rfind('\n', 0, at)+1
    pos = text.index('{', at)+1
    depth = 1
    while depth:
        depth += (text[pos] == '{')-(text[pos] == '}')
        pos += 1
    return text[start:pos]+'\n'


# Reuse hardware stubs from the r106 regression, not its success assumptions.
tree = ast.parse(blob('docs/tb371fc/recovery-state-r106/prepare_tests.py').decode('utf-8'))
literal = lambda name: next(ast.literal_eval(n.value) for n in tree.body
    if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in n.targets))
original_stub = literal('stub')
stub = original_stub
stub = stub.replace('struct dsi_display {struct panel *panel;const char *display_type;};',
    'struct dsi_bridge {bool r94_pre_enable_ok;};\n'
    'struct dsi_display {struct panel *panel;const char *display_type;struct dsi_bridge *bridge;};')
stub = stub.replace('struct drm_connector {struct {int id;} base;void *dev;};', r'''
struct drm_crtc_state {bool active,mode_changed,active_changed,connectors_changed;struct {int vrefresh;} mode;};
struct drm_crtc {struct drm_crtc_state *state;};
struct drm_connector_state {struct drm_crtc *crtc;int lp;};
struct drm_connector {struct {int id;} base;void *dev;struct drm_connector_state *state;void *panel;};
struct drm_atomic_state {struct drm_connector *connector;struct drm_connector_state *old_conn;
    struct drm_crtc_state *old_crtc;int count;};
struct drm_panel_notifier {void *data;int refresh_rate;unsigned int id;};
#define for_each_old_connector_in_state(s,c,old,i) \
    for((i)=0;(i)<(s)->count && (((c)=(s)->connector),((old)=(s)->old_conn),1);(i)++)
#define SDE_MODE_DPMS_LP2 2
#define SDE_MODE_DPMS_OFF 3
#define DRM_PANEL_BLANK_UNBLANK 0
#define DRM_PANEL_BLANK_POWERDOWN 1
#define DRM_PANEL_BLANK_LP 2
#define DRM_PANEL_BLANK_FPS_CHANGE 3
#define DRM_PANEL_EVENT_BLANK 1
#define DRM_PANEL_EARLY_EVENT_BLANK 2
#define CONNECTOR_PROP_LP 0
#define NOTIFY_STOP_MASK 0x8000
#define NOTIFY_OK 1
#define NOTIFY_BAD (NOTIFY_STOP_MASK | 2)
#define pr_debug(...) ((void)0)
static struct drm_crtc_state *drm_atomic_get_existing_crtc_state(struct drm_atomic_state *s,struct drm_crtc *c)
{(void)c;return s->old_crtc;}
static int sde_connector_get_property(struct drm_connector_state *s,int property)
{(void)property;return s->lp;}
static bool drm_atomic_crtc_needs_modeset(const struct drm_crtc_state *s)
{return s->mode_changed || s->active_changed || s->connectors_changed;}
static int next_notification,notifier_calls,observed_blank;
static bool dead_at_notifier,flag_at_notifier;
static void (*notifier_hook)(void);
static int drm_panel_notifier_call_chain(void *panel,unsigned long event,struct drm_panel_notifier *data);
void sde_connector_report_enable_failure(struct drm_connector *connector);
''')

tests = r'''
static struct panel p;
static struct dsi_display display;
static struct dsi_bridge bridge;
static struct sde_connector conn;
static struct encoder encoder;
static struct drm_crtc crtc;
static struct drm_crtc_state old_crtc,new_crtc;
static struct drm_connector_state old_conn,new_conn;
static struct drm_atomic_state atomic_state;
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
    display.bridge=&bridge;bridge.r94_pre_enable_ok=true;
    conn.display=&display;conn.encoder=&encoder;conn.connector_type=DRM_MODE_CONNECTOR_DSI;
    crtc.state=&new_crtc;
    new_crtc=(struct drm_crtc_state){.active=true,.mode={.vrefresh=144}};
    old_crtc=(struct drm_crtc_state){.active=false,.mode={.vrefresh=144}};
    new_conn=(struct drm_connector_state){.crtc=&crtc,.lp=SDE_MODE_DPMS_ON};
    old_conn=(struct drm_connector_state){.crtc=&crtc,.lp=SDE_MODE_DPMS_OFF};
    conn.base.state=&new_conn;conn.base.panel=&p;
    atomic_state=(struct drm_atomic_state){.connector=&conn.base,.old_conn=&old_conn,.old_crtc=&old_crtc,.count=1};
    on_calls=off_calls=fail_power=fail_pinctrl=fail_reset=notifications=events_with_false_payload=0;
    notifier_calls=0;next_notification=NOTIFY_OK;observed_blank=-1;
    notify_hook=backlight_hook=notifier_hook=0;
}
#define CHECK(x,label) do {checks++;if(!(x)){fprintf(stderr,"FAIL %s\n",label);failures++;}}while(0)
static void fault(void){_sde_connector_notify_panel_dead(&conn,true);}
static int drm_panel_notifier_call_chain(void *panel,unsigned long event,struct drm_panel_notifier *data)
{
    (void)panel;(void)event;notifier_calls++;observed_blank=*(int *)data->data;
    /* The real notifier runs outside the panel lock and may report a new fault. */
    assert(!pthread_mutex_trylock(&p.panel_lock));assert(!pthread_mutex_unlock(&p.panel_lock));
    dead_at_notifier=conn.panel_dead;flag_at_notifier=p.mi_cfg.panel_dead_flag;
    if(notifier_hook)notifier_hook();
    return next_notification;
}
static void begin(void){sde_connector_helper_bridge_pre_enable(&conn.base);}
static void post_on(void){sde_connector_helper_bridge_enable(&conn.base);}
static void complete(void){_sde_kms_drm_check_dpms(&atomic_state,DRM_PANEL_EVENT_BLANK);}
static void power_off(void)
{dsi_panel_acquire_panel_lock(&p);dsi_panel_power_off(&p);dsi_panel_release_panel_lock(&p);}
static void power_on(void)
{dsi_panel_acquire_panel_lock(&p);dsi_panel_power_on(&p);dsi_panel_release_panel_lock(&p);}

int main(void)
{
    fresh();begin();power_on();post_on();complete();power_off();
    CHECK(on_calls==0&&off_calls==0,"healthy sleep retains rails");
    CHECK(!conn.panel_dead&&!p.mi_cfg.panel_dead_flag&&notifications==0,"healthy completion invents no fault");
    CHECK(notifier_calls==1&&observed_blank==DRM_PANEL_BLANK_UNBLANK,"actual KMS path notifies native UNBLANK");

    fresh();fault();begin();power_off();power_on();post_on();
    CHECK(conn.panel_dead&&p.mi_cfg.panel_dead_flag,"post-on must not consume REK eligibility");
    complete();
    CHECK(dead_at_notifier&&flag_at_notifier,"dead flags remain until readiness callback");
    CHECK(!conn.panel_dead&&!p.mi_cfg.panel_dead_flag,"successful readiness consumes same fault generation");
    int before=off_calls;power_off();CHECK(off_calls==before,"successful readiness restores keep-power");

    fresh();fault();begin();power_on();post_on();next_notification=NOTIFY_BAD;complete();
    CHECK(conn.panel_dead&&p.mi_cfg.panel_dead_flag,"late REK failure retains both dead flags");
    CHECK(notifications==1,"failed recovery does not emit a second automatic recovery request");
    power_off();CHECK(off_calls==1,"late-failure native rollback retains rail-cycle eligibility");
    begin();power_on();post_on();complete();
    CHECK(notifications==1,"repeated failed native attempt stays coalesced");
    CHECK(conn.panel_dead&&p.mi_cfg.panel_dead_flag,"repeat failure never publishes success");
    begin();post_on();next_notification=NOTIFY_OK;complete();
    CHECK(!conn.panel_dead&&!p.mi_cfg.panel_dead_flag,"later real readiness can finish recovery");
    fault();CHECK(notifications==2,"independent new fault after success notifies once");

    fresh();begin();post_on();next_notification=NOTIFY_BAD;complete();
    CHECK(notifications==1&&conn.panel_dead&&p.mi_cfg.panel_dead_flag,"first normal-wake REK failure requests existing native recovery");
    begin();post_on();complete();CHECK(notifications==1,"failed requested recovery cannot self-loop notifications");

    fresh();fault();begin();post_on();notifier_hook=fault;complete();
    CHECK(conn.panel_dead&&p.mi_cfg.panel_dead_flag,"new fault inside readiness survives old success");
    CHECK(notifications==1,"concurrent fault still coalesces");
    notifier_hook=0;begin();post_on();complete();
    CHECK(!conn.panel_dead&&!p.mi_cfg.panel_dead_flag,"next complete generation clears");

    fresh();fault();begin();bridge.r94_pre_enable_ok=false;post_on();complete();
    CHECK(conn.panel_dead&&p.mi_cfg.panel_dead_flag,"blocked bridge cannot consume dead even on successful notifier");

    fresh();fault();begin();post_on();new_crtc.active=false;next_notification=NOTIFY_BAD;complete();
    CHECK(conn.panel_dead&&p.mi_cfg.panel_dead_flag&&notifications==1,"POWERDOWN notifier cannot finish or renotify recovery");
    fresh();fault();begin();post_on();new_conn.lp=SDE_MODE_DPMS_LP1;complete();
    CHECK(conn.panel_dead&&p.mi_cfg.panel_dead_flag,"LP callback cannot finish recovery");
    fresh();fault();begin();post_on();old_crtc.active=true;old_conn.lp=SDE_MODE_DPMS_ON;
    old_crtc.mode.vrefresh=120;complete();
    CHECK(observed_blank==DRM_PANEL_BLANK_FPS_CHANGE&&conn.panel_dead,"FPS-only callback cannot consume dead");
    fresh();fault();begin();post_on();_sde_kms_drm_check_dpms(&atomic_state,DRM_PANEL_EARLY_EVENT_BLANK);
    CHECK(conn.panel_dead&&p.mi_cfg.panel_dead_flag,"early UNBLANK cannot finish recovery");

    fresh();_sde_connector_notify_panel_dead(&conn,false);begin();post_on();complete();power_off();
    CHECK(!conn.panel_dead&&!p.mi_cfg.panel_dead_flag&&off_calls==0,"successful OFF/LP notify-only case keeps power policy");
    fresh();conn.connector_type=10;begin();post_on();complete();
    CHECK(notifications==0,"non-DSI display never acquires panel recovery work");

    fresh();fault();begin();post_on();conn.base.panel=0;complete();
    CHECK(conn.panel_dead&&p.mi_cfg.panel_dead_flag&&notifier_calls==0,"missing native callback cannot consume recovery");

    fresh();fault();begin();post_on();old_crtc.active=true;old_conn.lp=SDE_MODE_DPMS_ON;
    new_crtc.mode_changed=true;complete();
    CHECK(notifier_calls==1&&observed_blank==DRM_PANEL_BLANK_UNBLANK,
          "same-mode ON-to-ON native modeset still completes touch readiness");
    CHECK(!conn.panel_dead&&!p.mi_cfg.panel_dead_flag,"ON-to-ON recovery consumes only verified readiness");
    fresh();fault();begin();post_on();old_crtc.active=true;old_conn.lp=SDE_MODE_DPMS_ON;
    old_crtc.mode.vrefresh=120;new_crtc.mode_changed=true;complete();
    CHECK(observed_blank==DRM_PANEL_BLANK_UNBLANK&&!conn.panel_dead,
          "full modeset with FPS change prefers readiness over FPS-only notification");
    for(int kind=0;kind<2;kind++){
        fresh();fault();begin();post_on();old_crtc.active=true;old_conn.lp=SDE_MODE_DPMS_ON;
        if(kind==0)new_crtc.active_changed=true;else new_crtc.connectors_changed=true;
        complete();CHECK(notifier_calls==1&&!conn.panel_dead,"all native modeset predicates deliver readiness");
    }
    fresh();begin();post_on();old_crtc.active=true;old_conn.lp=SDE_MODE_DPMS_ON;
    new_crtc.mode_changed=true;next_notification=NOTIFY_BAD;complete();
    CHECK(notifications==1&&conn.panel_dead&&p.mi_cfg.panel_dead_flag,
          "ON-to-ON late failure requests one native recovery");
    new_crtc.mode_changed=false;complete();
    CHECK(notifier_calls==1&&notifications==1,"ordinary same-mode frames never poll or renotify touch recovery");
    fresh();_sde_connector_notify_panel_dead(&conn,false);begin();post_on();
    next_notification=NOTIFY_BAD;complete();
    CHECK(conn.panel_dead&&p.mi_cfg.panel_dead_flag&&notifications==1,
          "active readiness failure upgrades earlier notify-only fault without duplicate notification");
    printf("%d checks; %d failures\n",checks,failures);
    return failures?1:0;
}
'''

panel = blob('techpack/display/msm/dsi/dsi_panel.c').decode('utf-8')
notifier = blob('include/linux/notifier.h').decode('utf-8')
for kind in ['before','candidate']:
    connector = (W/kind/'techpack/display/msm/sde/sde_connector.c').read_text(encoding='utf-8')
    kms = (W/kind/'techpack/display/msm/sde/sde_kms.c').read_text(encoding='utf-8')
    functions = [function(notifier,'notifier_to_errno'),function(panel,'dsi_panel_power_on'),function(panel,'dsi_panel_power_off')]
    names = ['sde_connector_helper_bridge_pre_enable','sde_connector_helper_bridge_enable']
    if kind == 'candidate':
        names += ['sde_connector_complete_panel_recovery']
    names += ['_sde_connector_notify_panel_dead','sde_connector_report_enable_failure']
    functions += [function(connector,n) for n in names]
    functions += [function(kms,n) for n in ['_sde_kms_get_blank','_sde_kms_drm_check_dpms']]
    out = stub+'\nstatic bool p108_keep_panel_power = true;\n'+'\n'.join(functions)+tests
    (W/('contract-'+kind+'.c')).write_text(out,encoding='utf-8',newline='\n')
print('Extracted actual r106 and candidate KMS/connector call paths for host-only regression.')

# Keep r106's power/IRQ/notification regression, with success now including REK.
legacy_stub = original_stub.replace('struct dsi_display {struct panel *panel;const char *display_type;};',
    'struct dsi_bridge {bool r94_pre_enable_ok;};\n'
    'struct dsi_display {struct panel *panel;const char *display_type;struct dsi_bridge *bridge;};')
legacy_stub += '\nvoid sde_connector_report_enable_failure(struct drm_connector *connector);\n'
legacy_tests = literal('tests')
legacy_tests = legacy_tests.replace('static struct dsi_display display;',
    'static struct dsi_display display;\nstatic struct dsi_bridge bridge;')
legacy_tests = legacy_tests.replace('display.panel=&p;',
    'display.panel=&p;display.bridge=&bridge;bridge.r94_pre_enable_ok=true;')
legacy_tests = legacy_tests.replace('static void success(void){sde_connector_helper_bridge_enable(&conn.base);}',
    'static void success(void){sde_connector_helper_bridge_enable(&conn.base);sde_connector_complete_panel_recovery(&conn.base,0);}')
connector = (W/'candidate/techpack/display/msm/sde/sde_connector.c').read_text(encoding='utf-8')
legacy_names = ['sde_connector_helper_bridge_pre_enable','sde_connector_helper_bridge_enable',
                'sde_connector_complete_panel_recovery','_sde_connector_notify_panel_dead',
                '_sde_connector_report_panel_dead','sde_connector_report_enable_failure','esd_err_irq_handle']
legacy_functions = [function(panel,n) for n in ['dsi_panel_power_on','dsi_panel_power_off']]
legacy_functions += [function(connector,n) for n in legacy_names]
(W/'regression-r106.c').write_text(legacy_stub+'\nstatic bool p108_keep_panel_power = true;\n'
    +'\n'.join(legacy_functions)+legacy_tests,encoding='utf-8',newline='\n')
