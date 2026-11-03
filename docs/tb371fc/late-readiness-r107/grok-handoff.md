# Grok 接续：r107 与自然黑屏后的供电审阅

当前实机为功能提交 `41082098de91855a809239bf64f339a16d39effe`，本分支后续只补充维护证据，不改变已安装代码。正常启动及输入状态核对通过；INIT=0x9D／恢复后REK=A0起因和罕见恢复仍未证实修复。

- [统一交接入口：现状、真实证据与三个待碰撞问题](https://github.com/Qinyibo/TB371FC-ColorOS16/blob/main/docs/black-screen-handoff-20261103.md)
- [供电所有权的脱敏事实](panel-power-ownership-20261103.json)：vddio dummy、KTZ54/77/78未持有、触控/面板reset实际持有、真实断电未证明。
- [r106自然故障节选](r106-natural-failure-excerpt.txt)：9D硬复位失败→R104恢复→INIT成功→REK=A0。
- [r107修改与软件验证](README.md)：35项新增检查、35项回归、构建及安装范围。

厂家资料确认KTZ8866的0x09[0]外部使能模式，以及0x0F读清故障；详见统一交接中的官方链接。不要直接调用未使用的lcd_set_bias就宣称真实断电，也不要把GPIOINFO描述符当电压测量。未切供电GPIO、未新增补丁或继续刷机。
