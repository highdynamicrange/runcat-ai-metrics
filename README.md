# RunCat AI Metrics

为 [RunCat Neo](https://github.com/runcat-dev/RunCatNeo) 提供 Codex 用量与 DeepSeek 余额的非官方集成。使用原生 Custom Metrics 卡片，无需修改或重新编译 RunCat。

## 显示内容

| 集成 | 内容 | 刷新方式 |
|---|---|---|
| Codex | 账号额度已用比例、重置倒计时与进度条 | 对话结束刷新额度；每分钟更新倒计时 |
| Codex | 今日、近 7 天、近 30 天 token，30 日日均 | 对话结束读取本地日志并汇总 |
| DeepSeek | 官方 API 总可用余额；菜单栏金额 | 登录时及每小时查询一次 |

Token 只显示数字，采用 K／M／B（千／百万／十亿），最多两位小数。日期默认按北京时间；近 N 天包含今天，日均包含无使用日。DeepSeek 不统计 token。

## 安装

需要支持 Custom Metrics 的 RunCat Neo、Python 3.9+；Codex 集成另需 Node.js/npm。仅支持 macOS。

```bash
git clone https://github.com/highdynamicrange/runcat-ai-metrics.git
cd runcat-ai-metrics
python3 install.py all
# 或只安装其一：
# python3 install.py codex
# python3 install.py deepseek
```

安装器会备份并合并 `~/.codex/hooks.json`，保留其他 hooks；安装固定版本 `ccusage@20.0.26`。定时任务使用运行安装器的 Python 绝对路径，该解释器应长期保留。

### Codex

1. 重启 Codex，若出现提示，检查并信任新 hook。
2. 完成一轮对话，生成 `~/.codex/runcat-usage.json`。
3. 在 RunCat → Settings → Metrics → Custom Metrics 中添加这个文件。

如果当前 Codex 版本没有启用 hooks，可在现有 `~/.codex/config.toml` 的 `[features]` 中配置 `hooks = true`，避免重复添加节。首次配置后检查 hook 是否实际执行。

### DeepSeek

1. 打开 `~/.runcat/deepseek/config.json`，在 `api_key` 中填写官方 API key；**不要提交这个文件**。
2. 等待每小时刷新，或执行：

   ```bash
   python3 ~/.runcat/deepseek/update-deepseek.py
   ```

3. 在 RunCat 中添加 `~/.runcat/deepseek/deepseek.json`。

文件选择器可按 `⌘⇧G` 输入路径。要在菜单栏显示数值，打开 Metrics Bar 中对应来源的开关。

## 数据口径与异常

- Codex token 来源于保留的本地日志，不等于账号全设备总量或计费额度；已删除、其他设备及未落地的日志无法补算。统计依赖 [ccusage](https://github.com/ccusage/ccusage)，并使用离线、无价格模式。
- `not refreshed` 表示当前会话没有额度数据，正在显示旧额度。倒计时变动不表示已重新查询额度。
- 重置倒计时到零后显示等待新额度，不自行假定额度恢复。
- DeepSeek 显示官方 `/user/balance` 的 `total_balance`（充值余额与有效赠送余额）。不同币种分开显示。该接口没有历史 token 数据。
- 查询失败保留旧余额并显示失败状态；未配置 key 时显示配置提示。
- 没有自定义刷新按钮；不上传本地会话日志。API key 只用于官方 DeepSeek 余额请求。

## 卸载

```bash
python3 install.py all --uninstall
# 也可用 codex 或 deepseek 单独卸载
```

卸载移除本项目 hook 和定时任务，保留 API key、快照、脚本、ccusage 及备份。RunCat 中的数据源可以手动移除。

## 测试

```bash
python3 -m unittest discover -s codex -p 'test_*.py'
python3 -m unittest discover -s tests -p 'test_*.py'
```

## 来源与许可

采用 Apache-2.0，详见 [LICENSE](LICENSE) 和 [NOTICE](NOTICE)。本项目基于 RunCat Neo 的 Codex 自定义指标示例扩展，并参考 Bitcoin 示例的定时采集模式；不是 RunCat Neo、OpenAI 或 DeepSeek 官方项目。

新增内容包括 token 汇总、K/M/B 格式、倒计时刷新、DeepSeek 总余额，以及通用安装／卸载。ccusage 为独立安装的依赖，未将其源码复制进仓库。

[Codex 脚本说明](codex/README.md) · [DeepSeek 脚本说明](deepseek/README.md)
