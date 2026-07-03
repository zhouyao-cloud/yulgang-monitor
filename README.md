# yulgang-monitor
新熱血江湖世界舆情监控

## 功能

- 抓取 Bahamut、Google Play、App Store、Discord 舆情数据
- 写入 Google Sheet 原始数据表
- 生成运营日报/看板
- 推送飞书日报
- 在日报中标记本次数据源抓取异常，避免误把不完整数据当成正常结果

## GitHub Actions 配置

需要在仓库 Secrets 中配置：

- `GOOGLE_SERVICE_ACCOUNT_JSON`：Google Service Account JSON
- `FEISHU_WEBHOOK`：飞书机器人 Webhook
- `DISCORD_TOKEN`：Discord Bot Token

可选 Secrets：

- `SPREADSHEET_ID`：覆盖默认 Google Sheet ID
- `SHEET_URL`：覆盖日报按钮跳转链接

可选 Variables：

- `GAME_NAME`：覆盖游戏名称
- `DISCORD_FETCH_LIMIT`：每个 Discord 频道抓取消息数，默认 100
