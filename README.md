# site-human-annotator

一个基于 Flask + Supabase(PostgreSQL) + Vercel 的网站分类标注平台。

## 本地运行

1. 安装依赖

```bash
pip install -r requirements.txt
```

2. 配置环境变量（新建 `.env`）

```env
SECRET_KEY=your-secret
DATABASE_URL=postgresql://...
```

3. 启动

```bash
python annotation_platform/app.py
```

## Supabase 初始化

在 Supabase SQL Editor 执行 `supabase/migrations/init.sql` 建表。

## Vercel 部署

1. 在 Vercel 导入该 GitHub 仓库
2. 在 Vercel Project → Settings → Environment Variables 添加：
   - `DATABASE_URL`
   - `SECRET_KEY`
3. Deploy

