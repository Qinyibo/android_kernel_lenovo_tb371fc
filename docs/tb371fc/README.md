# TB371FC #43 开发记录

本目录补充当前完整源码如何对应实际构建、触控/唤醒和音频改动，以及历史测试的范围。完整ROM研究经过位于[移植仓库开发记录](https://github.com/Qinyibo/TB371FC-ColorOS16/tree/main/docs)。本次补充只增加材料，不改已发布的内核代码或配置。

## 源码基准与差异

历史构建目录没有保留Git历史，构建脚本又通过bind临时覆盖驱动文件、完工后恢复底树。因此本仓库初次导出时把当时实际编译的文件合入完整源，而不是上传恢复后的底树。原有版权、许可与上游来源继续保留。

[stock11-to-kernel43.patch](stock11-to-kernel43.patch)含11个触控/DSI/USB文件、两个音频文件和新增路由核心头，共14个文件。[patch-inputs.json](patch-inputs.json)列每个基准与结果SHA。基准是历史stock11文件，不是R94T v17，也不是适用于其他分支的通用补丁；本仓库源码已经含这些改动，不要再次应用。

本次已在独立基准文件副本上检查并应用该补丁，14份结果逐字节匹配公开源哈希。Windows验证时使用 `git -c core.autocrlf=false apply`；自动改成CRLF会令文本相同但SHA不匹配。这个补丁验证不等于内核重编验证。

当前Image与boot历史哈希、LLVM21、GNU aarch64工具链、完整config和构建环境说明见根目录 [README-TB371FC.md](../../README-TB371FC.md)及[构建入口](../../build/tb371fc/build.sh)。公开树尚未独立重编验证位级复现。原工具链runtime shim需要自己提供对应环境，不在此把构建脚本当作成功重建证据。

## IRQ、Hall、PM与面板转换

#43重点是IRQ wake单一所有权与Hall/PM转换同步。正常IRQ disable不在ts锁中等待；Hall相关工作trylock转换owner，避免与取消工作互相阻塞；PM suspend持owner再发布完成状态。固件异常先隔离输入包、关闭IRQ，再由正常面板PREPARE路径接管恢复，不靠猜测延时重新放行输入。

主要阅读 `drivers/input/touchscreen/nt36532/nt36xxx.c` 的 `nvt_irq_wake_ctrl_locked`、`nvt_runtime_failure_close_irq`、`nvt_hall_sleep_update`、`nvt_ts_pm_suspend/resume`、`nvt_panel_resume_prepare/arm/commit/abort`，再看DSI prepare/commit调用边界。底层与用户反馈之间仍有测试距离，不能据这些函数存在声称偶发黑屏或所有双击唤醒已根治。

## 测试材料的准确含义

[wake-owner-test-result.json](wake-owner-test-result.json)记录34个实际驱动/IRQ core失败与pthread用例，包含两种真实pthread交错和ASan/UBSan；硬件与workqueue原语被替换，不是板上压力测试。

[boundary-regression.py](boundary-regression.py)是历史源码边界测试生成入口，带原工作目录/输入结构，运行前需调整。本次公开它，不代表已在新公开Git树再跑一遍。[failure-tests-result.json](failure-tests-result.json)保持当时记录，不修改成新日期的成功。

真实板上已用这份 #43 boot完成v23双清首启和正常重启；物理双击、不同面板批次、长期偶发问题仍需单独验证。

## 四扬路由

`techpack/audio/asoc/codecs/tfa98xx` 的修改把请求/应答、generation及profile epoch放到同一驱动状态机。实际寄存器访问走DSP锁；状态核对依赖本机四颗功放地址、固件与revision。用户态轮转helper在[ROM仓库speaker](https://github.com/Qinyibo/TB371FC-ColorOS16/tree/main/speaker)，并对媒体、扬声器输出与NORMAL模式做门槛检查。通话归还失败不能当已归还。

## vnet外部模块

当前 `drivers/net/oplus_vnet` 是实际双栈适配源码，对应历史模块SHA256：

```
01cb1335daddcf308d11076af1db50f5386c6bb94312243b02197d1a7bfc66bd
```

最初找到的旧同名模块并不匹配；最终以实际v17/v23载荷哈希定位到正确产物与源。目录存在不代表内建进Image；应使用匹配的kernel output/config和符号CRC构建外部模块。模块能加载或接口存在，不等于真实手机共享数据/通话通过。
