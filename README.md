# 2026 高考志愿推荐模拟系统

一个可直接运行的 FastAPI + 原生 HTML/CSS/JavaScript 原型。系统按“位次为主、分数为辅”的原则，对 2023—2025 三年模拟投档数据进行加权，输出冲击、稳妥、保底三档建议。

分数输入会自动查询已导入的最新官方一分一段表。当前内置的是广东省教育考试院发布的 2025 年普通高考物理/历史分数段数据；2026 年夏季高考分数段发布后，加入 `app/data/score_rank_2026.csv` 即会自动优先采用新表。

> 数据为产品演示用途的模拟数据，不构成真实志愿填报或录取承诺。

## 启动

```bash
cd gaokao-volunteer
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

浏览器打开 <http://127.0.0.1:8000>，API 文档位于 <http://127.0.0.1:8000/docs>。

## 部署到公网

项目包含 `Dockerfile`，可直接部署到支持 Docker 的云平台；容器对外监听 `8000` 端口。若直接部署到 Linux 云服务器，也可沿用上面的启动命令，并用 Nginx 配置域名与 HTTPS。

## 测试

```bash
PYTHONPATH=. pytest -q
```

## 替换真实数据

按 `app/data/colleges.csv` 的字段格式导入经官方渠道核验的数据即可。生产环境应增加数据来源、发布时间、招生批次、专业备注，并由人工复核；也可将 `load_records()` 替换成 SQLAlchemy 查询。
