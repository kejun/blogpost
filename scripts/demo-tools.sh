#!/bin/bash
# Showboat & Rodney 快捷使用脚本
# 使用 uvx 运行，无需安装

# 显示帮助
show_help() {
    cat << 'EOF'
Showboat & Rodney - Agent 演示工具快捷脚本

用法:
  ./demo-tools.sh showboat [args]    # 运行 showboat
  ./demo-tools.sh rodney [args]      # 运行 rodney
  ./demo-tools.sh demo               # 创建示例演示
  ./demo-tools.sh help               # 显示此帮助

示例:
  ./demo-tools.sh showboat --help
  ./demo-tools.sh rodney --help
  
  # 创建演示文档
  ./demo-tools.sh showboat init demo.md "My Project"
  ./demo-tools.sh showboat note demo.md "Description here"
  ./demo-tools.sh showboat exec demo.md bash "echo Hello"

  # 浏览器自动化
  ./demo-tools.sh rodney start
  ./demo-tools.sh rodney open https://example.com
  ./demo-tools.sh rodney screenshot output.png
  ./demo-tools.sh rodney stop

EOF
}

# 检查 uvx 是否可用
if ! command -v uvx &> /dev/null; then
    echo "❌ uvx 未安装"
    echo "请安装 uv: https://github.com/astral-sh/uv"
    exit 1
fi

# 解析命令
case "$1" in
    showboat)
        shift
        echo "🎭 Running: uvx showboat $*"
        uvx showboat "$@"
        ;;
    rodney)
        shift
        echo "🌐 Running: uvx rodney $*"
        uvx rodney "$@"
        ;;
    demo)
        echo "🚀 创建示例演示..."
        
        # Showboat 示例
        echo ""
        echo "=== Showboat 示例 ==="
        uvx showboat init /tmp/demo.md "示例项目演示"
        uvx showboat note /tmp/demo.md "这是一个使用 Showboat 创建的演示文档"
        uvx showboat exec /tmp/demo.md bash "date"
        uvx showboat note /tmp/demo.md "当前时间如上所示"
        
        echo ""
        echo "✅ 演示文档已创建: /tmp/demo.md"
        echo ""
        
        # Rodney 示例（如果 Chrome 可用）
        if command -v google-chrome &> /dev/null || command -v chromium &> /dev/null || command -v chromium-browser &> /dev/null; then
            echo "=== Rodney 示例 ==="
            uvx rodney start
            uvx rodney open https://github.com
            uvx rodney js 'document.title'
            uvx rodney screenshot /tmp/rodney-demo.png
            uvx rodney stop
            echo "✅ 截图已保存: /tmp/rodney-demo.png"
        else
            echo "⚠️ Chrome/Chromium 未安装，跳过 Rodney 示例"
        fi
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        show_help
        ;;
esac
