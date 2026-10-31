# wake-cache-r1：已刷入版本与审阅入口

日期：2026-10-31。目标为 TB371FC ColorOS16 R94T v23，Linux 4.19.325-perf+。本目录对应实际刷入的上一版候选，不包含之后尚未完成的双击排查改动。

## 当前实机结论

- 已写入当前 a 槽boot，正常启动，Magisk root可用，没有双清。
- 一次电脑注入的短时熄屏/唤醒完成：固件文件请求计数保持1，缓存命中由0变1；真实REK检查通过后开放输入。注入WAKEUP不是物理双击验收。
- 用户明确反馈双击亮屏仍不工作。手动复现后未捕获到nvt_wake_key按键，手势上报计数仍为0。
- 用户反馈较长时间放置后，用电源键正常亮屏，以前需要强制重启。本次同一次开机标识仍在，但没有严格记录实际空闲时长、USB状态、保护套和深睡进入过程，因此只记作积极反馈，不宣布根治。
- 当前只读状态：gesture=1、hall_at_sleep=1、irq=1、irq_wake=1、gestures=0、pm_timeouts=0。未见本轮固件恢复失败或REK失败。累计IRQ计数包含亮屏触控，不能仅凭总数判断熄屏双击有没有产生中断。
- 本次读取的成功系统深休眠计数为0。它限制了这次自动测试的覆盖范围；不否认用户看到的长时间放置后恢复正常。

## 代码改动

真正改变内核行为的文件只有drivers/input/touchscreen/nt36532下的nt36xxx.c、nt36xxx.h、nt36xxx_fw_update.c。其余公开变化是构建标识、测试和说明。

1. 保留一份当前选定正常触控固件的引用。只有完整下载、原有CRC/INIT及固件信息读取成功才发布缓存；后续恢复复用文件数据，但仍重新解析、完整下载并经过原有校验。PREPARE → ARM → 原生UNBLANK/COMMIT顺序未改，REK门槛未删除。
2. 实机旧日志显示每次恢复都走用户态firmware sysfs fallback，超时节点为60秒，原始请求函数最多尝试3次。缓存消除首次成功之后的重复用户态文件依赖；这条阻塞可能性被确认存在，但没有故障现场证明它就是此前黑屏的唯一根因。
3. MP/工厂固件不缓存、不覆盖正常缓存。初始化失败、remove、shutdown都释放引用；失败的下载或固件信息读取不会发布新缓存。缓存不持有唤醒锁，也没有增加常驻轮询。
4. 增加无锁只读状态与计数。读取不会等待触控锁，不访问SPI，不改变屏幕状态。快照不是原子一致状态，errno/err_stage是最近一次记录的错误，不能单独当作最终失败结论。
5. 原来已经默认开启nvt_gesture_flag，双击仍映射KEY_POWER；本次没有虚构默认开关修复，也没有把按键换成KEY_WAKEUP。

配置与现有Module.symvers逐字节保持一致。boot只替换内核，ramdisk、DTB和其余载荷保持相同；头部只允许内核大小、摘要及派生位置变化。框架、微信/B站平行视窗、B站首页宽度和刷新率不在本次改动范围。

## Gemini／其他维护者优先看什么

先对照基线9bed5276d6526438208cd488b71292a725b68d4d与本版标签wake-cache-r1-20261031的三个触控文件，不要把全部历史修改算作本次补丁。

- nt36xxx_fw_update.c：缓存发布是否在成功校验之后，fw_entry与缓存别名释放，MP切换、失败重试和驱动退出时的生命周期。
- nt36xxx.c：nvt_ts_suspend中的0x13、Hall门槛及IRQ Wake；nvt_ts_work_func中的PM等待、SPI读取、包校验、手势解析与wake_input_dev上报；正常面板恢复阶段与缓存释放调用。
- nt36xxx.h：新增的缓存释放声明，其余触控常量未改。
- 双击仍未收到有效手势上报，不能先假设Android拦截了按键。还需分清芯片是否产生中断、手势包是否被读出/丢弃、睡眠模式及相关供电是否保持。
- 不要为了先点亮屏幕而删掉PREPARE错误返回、绕过固件校验或恢复异步固件下载。这些历史顺序约束没有被新的故障证据推翻。

## 构建与对应关系

本次实际构建从公开基线Git归档开始，应用三份列明的实际输入，使用原#43完整配置、LLVM21.1.8、GNU aarch64 binutils2.42，构建主机标识r94-wake-cache-r1，版本号仍#43，固定时间2026-10-31 12:00 +0800。这些是可识别候选的构建元数据，不是历史#43原版。

公开构建入口是build/tb371fc/build.sh，默认元数据已更新为本候选；本机实际构建入口保留在local-build.sh。build-receipt.json是打包时的历史快照，彼时尚未刷入；本页及validation.json补充之后的刷入和用户反馈。

- Image SHA256：58ffeb6e5776d622bd45f917bae4760c4fbb34229506a68e9df28b9769c8a0de
- 候选boot SHA256：8e0a355571cfdc04b749906b1056189fa94937d0e10f4d6f6e072a2c96a8cb8a
- 原版v23 boot SHA256：09d3c1bd67946575de8b0dad434f651e746747da2686fa227719142ad47cfbbe

完整内核已编译，12项抽取真实修改函数的测试通过ASan/UBSan，补丁已从基线重放并逐文件匹配最终输入。硬件、固件文件加载和下载操作在函数测试中是替身；它们不覆盖真实手势、SPI/PM交错和长待机。

## 状态节点

    /sys/module/nt36xxx/parameters/r94_wake_state
    /sys/module/nt36xxx_fw_update/parameters/r94_fw_cache_hits
    /sys/module/nt36xxx_fw_update/parameters/r94_fw_file_requests

stage：0初始、1触控休眠入口、2触控已休眠、3系统PM入口、4PM已挂起、5PM已恢复、6IRQ等PM、7手势已上报、8PREPARE入口、9固件恢复、10PREPARED、11ARMED、12COMMIT校验、13输入已恢复、14ABORT、15Hall关闭、16休眠WDT关闭。入口值可在无操作分支直接成功返回时保留，不能仅凭stage数值断言卡死。

## 本目录材料

source-manifest.json列三个源文件修改前后哈希；01/02补丁分别为固件缓存与只读诊断，当前main已包含，不要再次应用。test-firmware-cache.py在build/tb371fc，直接抽取当前源码执行测试。test-results.txt、kernel-build.log、build-input-verification.log和boot头/载荷核验日志是实际本机构建材料。没有上传原始用户数据、完整logcat、设备序列号、账号资料或原始聊天。
