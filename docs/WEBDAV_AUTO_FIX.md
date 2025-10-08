# WebDAV自动修复功能

## 功能说明

此功能会在所有下载任务完成后自动执行WebDAV嵌套目录修复，解决115云等存储服务中可能出现的嵌套目录结构问题。

## 配置方法

### 配置config.yaml

在您的`config.yaml`文件中添加以下`webdav`配置部分：

```yaml
alist:
  base_url: https://example.com
  token: alist-xxx
  downloader: qBittorrent
  download_path: Onedrive/Anime

webdav:
  url: "http://192.168.31.37:5244/dav"  # 您的Alist WebDAV地址
  username: "admin"
  password: "your_password"

  fixer:
    execute_mode: true        # 实际执行修复操作
    recursive_scan: true      # 递归扫描子目录
    conflict_strategy: "overwrite"  # 冲突处理策略
```

## 工作原理

1. **触发时机**:
   - 当所有下载任务完成时，在"All download tasks completed successfully"日志后自动执行
   - **新增**: 每次RSS检查完成后（包括"No new resources"情况）都会执行WebDAV修复检查
2. **执行逻辑**: 使用与`uv run alist-mikananirss webdav-fix`相同的修复逻辑
3. **配置共享**: 直接使用config.yaml中webdav部分的配置，无需额外配置文件
4. **日志输出**: 详细的修复过程和结果日志

## 日志示例

启用后，您将看到类似以下的日志输出：

### RSS检查完成后执行WebDAV修复
```
2025-10-08 04:10:43.816 | INFO | Start update checking
2025-10-08 04:10:44.669 | INFO | Converting torrent files to magnet links in RSS monitor...
2025-10-08 04:10:44.670 | INFO | No new resources
2025-10-08 04:10:44.671 | INFO | RSS check completed, next check in 21600 seconds
2025-10-08 04:10:44.672 | INFO | 开始执行WebDAV嵌套目录修复...
2025-10-08 04:10:44.673 | INFO | WebDAV认证信息: admin@http://192.168.31.37:5244/dav
2025-10-08 04:10:58.123 | INFO | 发现 0 个需要修复的嵌套目录
```

### 下载任务完成后执行WebDAV修复
```
2025-10-08 03:23:55.431 | INFO | All download tasks completed successfully
2025-10-08 03:23:55.432 | INFO | 开始执行WebDAV嵌套目录修复...
2025-10-08 03:23:56.123 | INFO | WebDAV认证信息: admin@http://192.168.31.37:5244/dav
2025-10-08 03:24:10.456 | INFO | 发现 3 个需要修复的嵌套目录:
2025-10-08 03:24:10.457 | INFO |  1. 目录: [桜都字幕组] 小城日常 [01][1080p][简体内嵌]
2025-10-08 03:24:10.458 | INFO |     文件: [桜都字幕组] 小城日常 [01][1080p][简体内嵌].mp4
2025-10-08 03:24:10.459 | INFO |     大小: 234.5 MB
2025-10-08 03:24:15.789 | INFO | WebDAV嵌套目录修复完成: 发现3个问题，成功修复3个
```

## 配置选项

### WebDAV配置 (config.yaml中的webdav部分)
- **url**: WebDAV服务器URL
- **username**: WebDAV用户名
- **password**: WebDAV密码
- **execute_mode**: `true`=实际执行, `false`=仅预览
- **recursive_scan**: 是否递归扫描子目录
- **conflict_strategy**: 冲突处理策略 (`skip`|`rename`|`overwrite`)

## 注意事项

1. **性能影响**: 修复过程会扫描指定的下载目录，大量文件时可能需要较长时间
2. **执行频率**: 现在每次RSS检查后都会执行，建议根据实际情况调整`recursive_scan`设置
3. **空间要求**: 确保WebDAV服务器有足够的存储空间进行文件操作
4. **权限设置**: 确保WebDAV用户有足够的读写权限
5. **备份建议**: 首次使用建议先设置`execute_mode: false`进行预览
6. **日志管理**: 频繁执行会产生更多日志，注意日志文件大小和保留策略

## 手动执行

如果您需要手动执行WebDAV修复，可以使用：

```bash
uv run alist-mikananirss webdav-fix --verbose --force
```

这将在所有任务完成后提供更详细的控制选项。