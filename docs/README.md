# Docs Index (GMV v3)

文档主入口：`docs/index.html`

## 线上发布（GitHub Pages）

仓库内置了自动部署工作流：`.github/workflows/pages.yml`。

推荐配置：

1. 打开仓库 `Settings -> Pages`
2. Source 选择 `GitHub Actions`
3. 推送 `main` 分支后自动发布

## 目录结构

- `docs/index.html`：前端说明站点
- `docs/assets/`：样式与交互脚本
- `docs/404.html`：Pages 路由兜底页
- `docs/archive/`：历史设计记录（不影响主文档）

## 说明

如果你当前在预览分支，Pages 可能不会更新到主站点 URL；请合并到 `main` 后再观察线上效果。
