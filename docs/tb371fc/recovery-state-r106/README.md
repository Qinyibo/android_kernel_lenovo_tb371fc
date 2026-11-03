# r106：恢复资格保留到成功提交

基于已公开 r104 功能代码和维护提交 `9dd8f4f9edee33052c4c52706131fe72e43f2ef5`。本项修正恢复状态生命周期，不宣称修复触控 INIT=0x9D 根因或已经验证异常硬件恢复。

## 问题与修改

旧代码在 `dsi_panel_power_on` 中清除 `panel_dead_flag`，此时 pinctrl、面板 reset 和后续 TOUCH_PREPARE 尚未全部完成。PREPARE 失败后 unprepare 的 power_off 被 p108 提前返回；connector 的 dead 状态仍为真，sticky 通知不会重新置位 panel 标志，后续尝试失去电源恢复资格。

- 删除 power_on 提前清理，失败后继续保留恢复资格。
- 使用已有 `panel_lock` 保护两个 dead 标志与故障序号，无新增锁。
- bridge pre-enable 开始前记录故障序号；原 helper_bridge_enable 成功提交点只有在序号未变时清理两个标志。
- 每次故障报告（包括 sticky 报告）更新故障序号，ESD IRQ 的 pending/dead 提前返回也计入。新故障不会被旧尝试的成功提交清掉。
- 外部 PANEL_DEAD 通知在释放 panel_lock 后发送，载荷使用稳定的局部 true，不引用可能刚被成功路径改变的状态字段。
- OFF/LP 的既有 notify-only 路径不请求电源恢复，普通休眠的 keep-power 策略保持原样。

只有四个产品源码文件变化：dsi_panel.c、dsi_drm.c、sde_connector.c/h。没有增加恢复线程、自动重通知、定时器或轮询，没有调整 IRQ 复位时序、固件/CRC、USB、调度、内存或键盘。

## 锁与调用顺序

新增状态访问复用 DSI panel_lock。调用者为 modeset 提交、ESD 工作或 threaded IRQ；现有 ESD 检查和 IRQ 路径在调用通知 helper 前已释放 connector/panel 锁。通知、encoder recovery 和背光调用不在新增 panel_lock 临界区内，避免扩展为跨回调持锁。

成功提交仅关闭开始前的故障代次；如果恢复期间出现新故障，仍保留 dead 状态。既有 sticky 通知合并策略不增加重试，保留状态不等于保证自动再次恢复。

## 已完成的软件验证

直接抽取原版/候选的 power_on、power_off、bridge helper、notify/report 和 ESD IRQ 函数，硬件调用替换为受控 stub。使用 pthread 及 UBSan 测试失败回退和通知交错，不能当作真实电气、GPIO 波形或内核压力验证。

- 原版共有检查 29 项，其中 13 项失败；候选相同检查通过，另加 6 项候选检查，共 35 项通过。
- 覆盖首次恢复、PREPARE/post-enable 失败回退、上电/pinctrl/reset 返回错误、再次尝试、成功恢复后正常休眠、新故障在提交前后及通知中交错、ESD 提前返回、OFF/LP 策略和并发报告合并。
- checkpatch：0 错误、0 警告。完整 Image 构建通过，配置与 Module.symvers 未变，继承的编译警告仍存在。
- 未刷入的 r100 HID 候选和撤回的 r105 USB 候选均不包含；构建完成后恢复工作区原文件（包括原有 CRLF），候选源码由此 Git 提交独立保存。

在本分支的完整 Git checkout 中生成并运行回归（Linux host，非平板）：

```sh
python3 docs/tb371fc/recovery-state-r106/prepare_tests.py "$PWD" /tmp/r106-contract
clang -Wall -Wextra -Werror -Wno-unused-function -Wno-unused-parameter -Wno-misleading-indentation -fsanitize=undefined -pthread /tmp/r106-contract/contract-before.c -o /tmp/r106-before
/tmp/r106-before # 预期返回1并报告原版缺陷
clang -Wall -Wextra -Werror -Wno-unused-function -Wno-unused-parameter -Wno-misleading-indentation -fsanitize=undefined -pthread -DCANDIDATE /tmp/r106-contract/contract-candidate.c -o /tmp/r106-candidate
/tmp/r106-candidate
```

完整内核沿用 `build/tb371fc/build.sh`，设置 `KBUILD_BUILD_HOST=r106-recovery-state`。启动镜像以精确 r104 boot 为基线，仅替换内核；ramdisk、DTB 和其他载荷及 header 不变量逐项比较。

## 实机边界与回退

当前构建/安装状态以同目录 validation.json 为准。后续只做一次正常安装与启动核对，不故障注入、不反复唤醒。异常恢复和 INIT=0x9D 仍需自然故障现场验证。

回退到 r104 boot SHA256 `f29c32c15c7276d777f243a322ca35495099c25d6e41e402dd4eacb77121f85b`。不改变 ROM/data，也不使用失败的 fastboot RAM 下载载荷。
