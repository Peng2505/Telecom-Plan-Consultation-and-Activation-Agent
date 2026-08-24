# 发布到 GitHub

1. 打开 https://github.com/new 建一个空仓库（不要勾选 README）。
2. 在本目录执行（把 URL 换成你的）：

```bat
cd /d D:\data-plan-langgraph-agent
git remote add origin https://github.com/你的用户名/仓库名.git
git push -u origin main
```

本目录已经 `git init` 并做好首次提交。不要添加 `.env`。
