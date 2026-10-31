from pathlib import Path
import re
import subprocess
import argparse
import tempfile

here=Path(__file__).resolve().parent
parser=argparse.ArgumentParser()
parser.add_argument('--source',type=Path,default=here.parents[1]/'drivers/input/touchscreen/nt36532/nt36xxx_fw_update.c')
args=parser.parse_args()
source=args.source.read_text()
def function(name):
    match=re.search(r'^(?:static\s+)?(?:void|int32_t)\s+'+name+r'\([^;]*?\)\s*\{',source,re.M)
    assert match,name
    start=source.index('{',match.start())
    depth=1
    i=start+1
    while depth:
        depth+=(source[i]=='{')-(source[i]=='}')
        i+=1
    return source[match.start():i]

prefix=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#define NVT_LOG(...) ((void)0)
#define NVT_ERR(...) ((void)0)
#define lockdep_assert_held(p) assert(*(p)==1)
#define IS_ERR_OR_NULL(p) (!(p))
#define unlikely(x) (x)
#define kfree(p) free(p)
#define FW_BIN_VER_OFFSET 0
#define FW_BIN_VER_BAR_OFFSET 1
struct firmware {size_t size; uint8_t *data;};
static const struct firmware *fw_entry,*nvt_boot_fw_cache;
static unsigned int nvt_fw_cache_hits,nvt_fw_file_requests;
static void *bin_map;
static char *BOOT_UPDATE_FIRMWARE_NAME="normal.bin";
static struct client {int dev;} client;
static struct {int lock,hw_crc,fw_update_stat; struct client *client; void *nvt_charger_notify_wq; int charger_notify_work;} device={.lock=1,.hw_crc=1,.client=&client},*ts=&device;
static int acquired,released,requests,downloads,loader_error,parse_error,download_error,init_error,info_error;
static int request_firmware(const struct firmware **out,const char *name,void *dev){
    (void)name;(void)dev;requests++;
    *out=NULL;
    if(loader_error)return loader_error;
    struct firmware *f=malloc(sizeof(*f));assert(f);
    f->size=16;f->data=calloc(16,1);assert(f->data);
    f->data[0]=0x12;f->data[1]=0xED;*out=f;acquired++;return 0;
}
static void release_firmware(const struct firmware *f){if(f){free(f->data);free((void*)f);released++;}}
static int nvt_get_fw_need_write_size(const struct firmware *f){assert(f&&f->size==16);return 0;}
static int nvt_bin_header_parser(const uint8_t *p,size_t n){assert(p&&n==16);bin_map=malloc(8);assert(bin_map);return parse_error;}
static int nvt_download_init(void){return init_error;}
static int nvt_download_firmware_hw_crc(void){assert(fw_entry&&bin_map);downloads++;return download_error;}
static int nvt_download_firmware(void){return nvt_download_firmware_hw_crc();}
static int nvt_get_fw_info(void){return info_error;}
static void queue_work(void *q,int *w){(void)q;(void)w;}
'''
tests=r'''
static void reset(void){
    nvt_firmware_cache_release();assert(!fw_entry&&!bin_map);
    assert(acquired==released);
    acquired=released=requests=downloads=loader_error=parse_error=download_error=init_error=info_error=0;
    nvt_fw_cache_hits=nvt_fw_file_requests=0;BOOT_UPDATE_FIRMWARE_NAME="normal.bin";
}
int main(void){
    assert(!nvt_update_firmware("normal.bin"));
    assert(nvt_boot_fw_cache&&!fw_entry&&requests==1&&downloads==1&&acquired-released==1);
    loader_error=-ETIMEDOUT;
    assert(!nvt_update_firmware("normal.bin"));
    assert(requests==1&&downloads==2&&nvt_fw_cache_hits==1);
    puts("PASS warm_resume_downloads_and_validates_without_userspace_request");
    loader_error=0;const struct firmware *normal=nvt_boot_fw_cache;
    assert(!nvt_update_firmware("factory.bin"));
    assert(nvt_boot_fw_cache==normal&&requests==2&&acquired-released==1);
    assert(!nvt_update_firmware("normal.bin")&&requests==2);
    puts("PASS factory_image_never_replaces_or_releases_normal_cache");
    reset();download_error=-EIO;
    assert(nvt_update_firmware("normal.bin")==-EIO);
    assert(!nvt_boot_fw_cache&&!fw_entry&&acquired==released);
    puts("PASS failed_device_CRC_download_cannot_publish_cache");
    reset();info_error=-EIO;
    assert(nvt_update_firmware("normal.bin")==-EIO&&!nvt_boot_fw_cache&&acquired==released);
    puts("PASS failed_firmware_info_cannot_publish_cache");
    reset();parse_error=-EINVAL;
    assert(nvt_update_firmware("normal.bin")==-EINVAL&&requests==3&&!nvt_boot_fw_cache&&!bin_map&&acquired==released);
    puts("PASS parser_errors_keep_bounded_retries_and_free_all_allocations");
    reset();loader_error=-ETIMEDOUT;
    assert(nvt_update_firmware("normal.bin")==-ETIMEDOUT&&requests==3&&!nvt_boot_fw_cache&&!fw_entry);
    puts("PASS initial_loader_failure_remains_bounded_and_does_not_fake_success");
    reset();init_error=-ENOMEM;
    assert(nvt_update_firmware("normal.bin")==-ENOMEM&&!nvt_boot_fw_cache&&!bin_map&&acquired==released);
    puts("PASS download_buffer_failure_releases_uncached_firmware");
    reset();assert(!nvt_update_firmware("normal.bin"));normal=nvt_boot_fw_cache;
    download_error=-EIO;
    assert(nvt_update_firmware("normal.bin")==-EIO&&nvt_boot_fw_cache==normal&&requests==1);
    download_error=0;loader_error=-ETIMEDOUT;
    assert(!nvt_update_firmware("normal.bin")&&requests==1&&downloads==3);
    puts("PASS cached_recovery_still_obeys_download_error_and_can_retry_next_transaction");
    reset();assert(!nvt_update_firmware("normal.bin"));
    nvt_boot_fw_cache->data[0]=0;
    assert(!nvt_update_firmware("normal.bin")&&requests==2&&acquired-released==1);
    puts("PASS invalid_cached_header_is_evicted_before_fresh_load");
    reset();BOOT_UPDATE_FIRMWARE_NAME=NULL;
    assert(!nvt_update_firmware("factory.bin")&&!nvt_boot_fw_cache&&acquired==released);
    puts("PASS absent_boot_name_does_not_cache_factory_firmware");
    reset();assert(!nvt_update_firmware("normal.bin"));fw_entry=nvt_boot_fw_cache;
    nvt_firmware_cache_release();
    assert(!fw_entry&&!nvt_boot_fw_cache&&acquired==released);
    update_firmware_release();
    puts("PASS teardown_clears_alias_without_double_release");
    reset();for(int i=0;i<100;i++)assert(!nvt_update_firmware("normal.bin"));
    assert(requests==1&&downloads==100&&nvt_fw_cache_hits==99);
    reset();puts("PASS repeated_off_on_ownership_has_no_leaks");
    return 0;
}
'''
actual='\n\n'.join(function(n) for n in ['nvt_firmware_cache_release','update_firmware_release','update_firmware_request','nvt_update_firmware'])
with tempfile.TemporaryDirectory(prefix='tb371fc-fw-cache-') as temporary:
    folder=Path(temporary)
    c=folder/'test.c';binary=folder/'test'
    c.write_text(prefix+actual+tests)
    subprocess.run(['gcc','-std=gnu11','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-g',str(c),'-o',str(binary)],check=True)
    result=subprocess.run([str(binary)])
    raise SystemExit(result.returncode)
