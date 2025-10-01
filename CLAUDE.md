# Claude 执行环境记录

## Git Bash 路径转换问题

**问题描述：**
在 Git Bash 环境中执行脚本时，传递 Unix 风格路径参数（如 `/115/TV/魔女守护者`）会被 Bash 自动转换为 Windows 绝对路径格式（如 `J:/Program Files/Git/115/TV/魔女守护者`），导致 WebDAV 操作失败。

**测试结果：**
- Git Bash: `/115/TV/魔女守护者` → `J:/Program Files/Git/115/TV/魔女守护者` ❌
- PowerShell: 参数保持原样 ✅

**解决方案：**
使用 PowerShell 环境执行脚本，避免路径自动转换。

**执行命令：**
```powershell
python fix_nested_structure_webdav_final.py --url http://127.0.0.1:5244/dav --username admin --password 1234 --dir "/115/TV/魔女守护者" --verbose --force
```