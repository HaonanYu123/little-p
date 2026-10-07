# 参与贡献

欢迎提交问题和改进。开始修改前，请先确认相关内容允许以非商业方式分发，并保留 `THIRD_PARTY_NOTICES.md` 中列出的上游许可。

本地启动：

```powershell
start.bat
```

网页地址为 <http://127.0.0.1:8086/>。修改 Python 或 JavaScript 后，至少运行语法检查：

```powershell
python -m py_compile runtime_paths.py desktop_host.py desktop/pet.py desktop/menu.py littlep_app.py serve.py
node --check site/app.js
```

提交信息请写明最终行为，例如 `fix: restore desktop summon from hosted page`。
