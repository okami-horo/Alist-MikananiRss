# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Alist-MikananiRss is an automated RSS-based anime download manager that:
- Fetches anime updates from Mikan Project RSS feeds or other anime-related RSS sources
- Downloads files through Alist's integrated downloaders (qBittorrent/Aria2) to cloud storage
- Renames files using AI analysis (ChatGPT/OpenAI/Google) to Emby-compatible formats
- Sends notifications via multiple channels (Telegram, PushPlus)
- Includes a Telegram bot assistant for remote management

## Core Architecture

The application follows a modular architecture with these key components:

### Core Modules (`src/alist_mikananirss/core/`)
- **RssMonitor**: Monitors RSS feeds and triggers downloads
- **DownloadManager**: Manages download tasks through Alist
- **AnimeRenamer**: Handles AI-powered file renaming
- **NotificationSender**: Manages multi-channel notifications
- **BotAssistant**: Telegram bot for remote management
- **RegexFilter**: Filters RSS content based on patterns

### Alist Integration (`src/alist_mikananirss/alist/`)
- **Alist API client**: Communicates with Alist server (requires v3.42.0+)
- **Task monitoring**: Tracks download progress and completion

### Configuration System (`src/alist_mikananirss/common/config/`)
- **Pydantic-based configuration**: Type-safe configuration management
- **YAML configuration files**: Human-readable config format
- **Environment-specific configs**: Supports different deployment scenarios

### AI Integration (`src/alist_mikananirss/extractor/`)
- **Multiple LLM providers**: OpenAI, Google Gemini, and other AI providers
- **Prompt templates**: Structured prompts for consistent anime name extraction
- **JSON schema output**: Ensures structured AI responses for renaming

## Development Commands

### Running the Application
```bash
# Development installation
pip install -e .

# Run with configuration file
python -m alist_mikananirss --config config.yaml

# Direct Python execution
./venv/bin/python -m alist_mikananirss --config config.yaml
```

### Testing
```bash
# Run all tests
pytest

# Run specific test module
pytest tests/core/test_download_manager.py

# Run with coverage
pytest --cov=src/alist_mikananirss

# Async tests are configured with auto mode in pytest.ini
```

### Code Quality
```bash
# Linting
ruff check src/

# Formatting
black src/

# Type checking (if using mypy)
mypy src/
```

### Development Environment
- **Python**: Requires Python 3.11+
- **Dependencies**: Managed with uv (see uv.lock) or pip
- **Virtual environment**: Can use either venv/ or .venv/

## Configuration

### Basic Configuration (`config.yaml`)
```yaml
common:
  interval_time: 300  # RSS check interval in seconds

alist:
  base_url: https://example.com
  token: alist-xxx
  downloader: qBittorrent  # or aria2
  download_path: Onedrive/Anime

mikan:
  subscribe_url:
    - https://mikanani.me/RSS/MyBangumi?token=xxx
  filters:
    - 非合集  # Filter out collections
```

### Advanced Features
- **AI Renaming**: Configure OpenAI/Google API for intelligent file renaming
- **Notifications**: Multi-channel notification setup (Telegram, PushPlus)
- **Bot Assistant**: Telegram bot for remote management
- **Remapping**: Custom mapping rules for renaming corrections
- **Proxy Support**: HTTP/HTTPS proxy configuration

## Special Tools

### WebDAV Structure Fix
The repository includes a specialized tool for fixing nested directory structures in WebDAV:

```bash
./venv/bin/python fix_nested_structure_webdav_final.py --url http://127.0.0.1:5244/dav --username admin --password [password] --dir "/115/TV/2025-07" --recursive --verbose --force
```

This tool:
- Scans WebDAV directories for nested structures
- Moves files from nested directories to target locations
- Cleans up empty directories
- Provides detailed operation logging

## Key Dependencies

### Core Dependencies
- **aiohttp**: Async HTTP client for API calls
- **feedparser**: RSS feed parsing
- **loguru**: Structured logging
- **pydantic**: Data validation and configuration management
- **PyYAML**: YAML configuration file support

### AI/ML Dependencies
- **openai**: OpenAI API client
- **google-genai**: Google AI API client

### Bot Dependencies
- **python-telegram-bot**: Telegram bot API
- **beautifulsoup4**: HTML parsing for web content

### Development Dependencies
- **pytest**: Testing framework with async support
- **aioresponses**: Mock HTTP responses for testing
- **ruff**: Fast Python linter
- **black**: Code formatter

## Database

Uses SQLite for storing subscription history and download metadata. Database operations are handled through `SubscribeDatabase` class in `src/alist_mikananirss/common/database.py`.

## Logging

Configured through loguru with:
- File rotation: Daily at midnight
- Retention: 7 days
- Console and file output
- Configurable log levels via `dev.log_level` in config

## Docker Support

The project supports containerized deployment with Docker configuration in the `docker/` directory.

修复指令：
  # 查看帮助
  uv run alist-mikananirss webdav-fix --help

  # 预览模式（不实际执行）
  uv run alist-mikananirss webdav-fix --dir "/115/TV/2025-07" --verbose

  # 实际执行修复
  uv run alist-mikananirss webdav-fix --dir "/115/TV/2025-07" --force --verbose

  # 递归扫描
  uv run alist-mikananirss webdav-fix --dir "/115/TV" --recursive --force
  
 always answer in chinese