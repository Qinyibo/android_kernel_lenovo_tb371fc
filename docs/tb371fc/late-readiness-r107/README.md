# r107：在原生触控就绪后完成面板恢复

bridge post-enable 只完成面板后置命令并 ARM 触控；真正的 REK 检查发生在 KMS native complete-commit 的 UNBLANK 通知。自然故障中，固件 INIT 下载成功后 REK 仍停 A0，返回 NOTIFY_BAD。r106 已提前清除 dead 标志，KMS 又忽略该错误，造成恢复被过早视为成功。

仅修改 sde_connector.c/h 与 sde_kms.c：两份 dead 状态保留到就绪通知成功后，沿用 r106 的 panel_lock 与故障序号；错误使用现有 sticky PANEL_DEAD 合并流程。已合并的通知不丢弃后续 active 故障的电源恢复资格，OFF/LP notify-only 本身保持原策略。

完整 ON→ON modeset 即使 DPMS 和 FPS 相同也要完成就绪通知，使用既有 drm_atomic_crtc_needs_modeset 条件；纯 FPS 更新和普通帧不增加触控提交。没有新增状态字段、重试线程、定时器或轮询，没有伪造 REK、强开 IRQ 或在 SDE 活动时私自拆卸 DSI。

35 项新增提取生产函数检查：r106 失败21项、r107全部通过；沿用35项电源/IRQ/通知交错回归也全部通过。使用硬件 stub、pthread 与 UBSan，不等于真实芯片或电气验证。完整 Image、配置/Module.symvers、启动镜像非内核载荷/头部、分区完整回读及一次正常启动核对均通过。原生启动、Enforcing 和输入驱动状态正常，原版 bdd74 Launcher 在全局和实际进程命名空间核验一致。未清数据，未做故障注入或唤醒压力测试。

**INIT=0x9D、恢复后 REK=A0 的起因与罕见黑屏恢复仍未证实修复。** 此提交是恢复契约修正，普通启动不能替代罕见故障和长期稳定性验收。未集成到 v27 整包。

在完整 Git checkout 内生成回归：

```sh
python3 docs/tb371fc/late-readiness-r107/prepare_tests.py "$PWD" /tmp/r107-contract
clang -Wall -Wextra -Werror -Wno-unused-function -Wno-unused-parameter -Wno-misleading-indentation -fsanitize=undefined -pthread /tmp/r107-contract/contract-before.c -o /tmp/r107-before
/tmp/r107-before # 预期35项中21项失败，退出1
clang -Wall -Wextra -Werror -Wno-unused-function -Wno-unused-parameter -Wno-misleading-indentation -fsanitize=undefined -pthread /tmp/r107-contract/contract-candidate.c -o /tmp/r107-candidate
/tmp/r107-candidate
clang -Wall -Wextra -Werror -Wno-unused-function -Wno-unused-parameter -Wno-misleading-indentation -fsanitize=undefined -pthread -DCANDIDATE /tmp/r107-contract/regression-r106.c -o /tmp/r107-legacy
/tmp/r107-legacy
```

完整内核沿用 build/tb371fc/build.sh，KBUILD_BUILD_HOST=r107-late-readiness。最终 boot100663296B SHA256 `372004d3e4ad7985c58f9eade4961aa89a30ef8a5605e57e09eea0309e7129de`；回退至 r106 boot SHA256 `899860494f70ec1b63241a9ebbd25946502bdb7e932558bc114632f908ae0920`。只替换内核，原 ramdisk/DTB 和其他载荷保持逐字节一致。
