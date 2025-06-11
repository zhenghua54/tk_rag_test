#!/bin/bash
#
# Kibana 一键安装部署脚本
# 用途：自动安装并配置与当前ES版本匹配的Kibana
# 作者：Claude
# 日期：2025-06-11
#

# 设置颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # 无颜色

# ES配置
ES_HOST="http://localhost:9200"
ES_USER=""
ES_PASSWORD=""

# 端口配置
KIBANA_PORT=5601
ES_PORT=9200

# 输出带颜色的信息函数
info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查是否以root用户运行
if [ "$(id -u)" != "0" ]; then
    error "必须以root用户运行此脚本。请使用 sudo 命令。"
    exit 1
fi

# 配置防火墙
configure_firewall() {
    info "配置防火墙规则..."

    # 检查是否安装了ufw
    if command -v ufw &> /dev/null; then
        info "检测到ufw防火墙，配置规则..."
        # 检查ufw是否启用
        if ufw status | grep -q "Status: active"; then
            # 允许Kibana端口
            ufw allow $KIBANA_PORT/tcp
            # 允许ES端口
            ufw allow $ES_PORT/tcp
            success "已配置ufw防火墙规则"
        else
            warning "ufw防火墙未启用，跳过配置"
        fi
    fi

    # 检查是否安装了firewalld
    if command -v firewall-cmd &> /dev/null; then
        info "检测到firewalld防火墙，配置规则..."
        # 检查firewalld是否运行
        if systemctl is-active --quiet firewalld; then
            # 允许Kibana端口
            firewall-cmd --permanent --add-port=$KIBANA_PORT/tcp
            # 允许ES端口
            firewall-cmd --permanent --add-port=$ES_PORT/tcp
            # 重新加载防火墙配置
            firewall-cmd --reload
            success "已配置firewalld防火墙规则"
        else
            warning "firewalld防火墙未运行，跳过配置"
        fi
    fi

    # 检查是否安装了iptables
    if command -v iptables &> /dev/null; then
        info "检测到iptables，配置规则..."
        # 允许Kibana端口
        iptables -A INPUT -p tcp --dport $KIBANA_PORT -j ACCEPT
        # 允许ES端口
        iptables -A INPUT -p tcp --dport $ES_PORT -j ACCEPT
        # 保存iptables规则
        if command -v iptables-save &> /dev/null; then
            iptables-save > /etc/iptables/rules.v4
        fi
        success "已配置iptables规则"
    fi
}

# 配置Kibana远程访问
configure_kibana_remote() {
    info "配置Kibana远程访问..."

    # 获取本机IP地址
    SERVER_IP=$(hostname -I | awk '{print $1}')
    
    # 修改Kibana配置
    cat > /etc/kibana/kibana.yml <<EOF
# Kibana配置文件
# 监听端口
server.port: ${KIBANA_PORT}

# 允许从所有IP访问Kibana
server.host: "0.0.0.0"

# 允许跨域访问
server.cors.enabled: true
server.cors.allowOrigin: ["*"]

# Elasticsearch连接设置
elasticsearch.hosts: ["${ES_HOST}"]
EOF

    # 如果启用了安全认证，添加认证信息
    if [ -n "$ES_USER" ] && [ -n "$ES_PASSWORD" ]; then
        cat >> /etc/kibana/kibana.yml <<EOF
elasticsearch.username: "${ES_USER}"
elasticsearch.password: "${ES_PASSWORD}"
EOF
    fi

    cat >> /etc/kibana/kibana.yml <<EOF
# 日志设置
logging.dest: /var/log/kibana/kibana.log

# 其他设置
server.maxPayloadBytes: 1048576
elasticsearch.requestTimeout: 30000
EOF

    # 设置Kibana目录权限
    chown -R kibana:kibana /etc/kibana
    chmod -R 755 /etc/kibana

    success "Kibana远程访问配置完成"
    info "Kibana将监听在: 0.0.0.0:${KIBANA_PORT}"
}

# 获取ES认证信息
get_es_credentials() {
    # 如果已经通过版本检查获取了认证信息，直接返回
    if [ -n "$ES_VERSION" ]; then
        return
    fi

    # 首先尝试从环境变量获取
    if [ -n "$ES_USER" ] && [ -n "$ES_PASSWORD" ]; then
        info "从环境变量获取ES认证信息"
        return
    fi

    # 如果环境变量未设置，提示用户输入
    info "请输入ES认证信息"
    read -p "用户名 (默认: elastic): " input_user
    ES_USER=${input_user:-"elastic"}
    
    read -sp "密码: " input_password
    echo
    ES_PASSWORD=$input_password

    # 验证认证信息
    if ! curl -s -u "${ES_USER}:${ES_PASSWORD}" "${ES_HOST}" > /dev/null; then
        error "认证失败，请检查用户名和密码"
        exit 1
    fi
}

# 初始化ES安全认证
init_es_security() {
    info "检测到ES未启用安全认证，开始初始化安全认证..."

    # 获取ES版本
    ES_VERSION=$(curl -s "${ES_HOST}" | jq -r '.version.number')
    if [ -z "$ES_VERSION" ]; then
        error "无法获取ES版本信息"
        exit 1
    fi

    # 根据版本选择初始化命令
    if [[ "$ES_VERSION" == "7."* ]]; then
        info "检测到ES 7.x版本，使用elasticsearch-setup-passwords命令"
        ES_SETUP_CMD="elasticsearch-setup-passwords"
    elif [[ "$ES_VERSION" == "8."* ]]; then
        info "检测到ES 8.x版本，使用elasticsearch-reset-password命令"
        ES_SETUP_CMD="elasticsearch-reset-password"
    else
        error "不支持的ES版本: $ES_VERSION"
        exit 1
    fi

    # 设置默认密码
    if [ -z "$ES_PASSWORD" ]; then
        ES_PASSWORD="Nihao123!"
        info "使用默认密码: $ES_PASSWORD"
    fi

    # 执行密码设置
    if [[ "$ES_VERSION" == "7."* ]]; then
        # ES 7.x
        echo "y" | $ES_SETUP_CMD auto
        ES_USER="elastic"
    elif [[ "$ES_VERSION" == "8."* ]]; then
        # ES 8.x
        $ES_SETUP_CMD -u elastic -i
        ES_USER="elastic"
    fi

    success "ES安全认证初始化完成"
    info "用户名: $ES_USER"
    info "密码: $ES_PASSWORD"
}

# 检查依赖
install_dependencies() {
    info "检查所需依赖: curl, jq..."

    if ! command -v curl &> /dev/null; then
        info "未检测到 curl，开始安装..."
        apt-get update && apt-get install -y curl
    else
        success "curl 已安装"
    fi

    if ! command -v jq &> /dev/null; then
        info "未检测到 jq，开始安装..."
        apt-get update && apt-get install -y jq
    else
        success "jq 已安装"
    fi
}

# 检查当前安装的ES版本
check_es_version() {
    info "检查当前安装的Elasticsearch版本..."

    # 设置默认认证信息
    if [ -z "$ES_USER" ]; then
        ES_USER="elastic"
    fi
    if [ -z "$ES_PASSWORD" ]; then
        ES_PASSWORD="Nihao123!"
    fi

    # 等待ES服务响应（最多等 30 秒）
    for i in {1..6}; do
        # 尝试带认证访问
        RESPONSE=$(curl -s -u "${ES_USER}:${ES_PASSWORD}" "${ES_HOST}")
        if [ -n "$RESPONSE" ]; then
            ES_VERSION=$(echo "$RESPONSE" | jq -r '.version.number')
            if [[ -n "$ES_VERSION" && "$ES_VERSION" != "null" ]]; then
                success "检测到Elasticsearch版本: $ES_VERSION"
                return
            fi
        fi

        # 如果带认证访问失败，尝试无认证访问
        RESPONSE=$(curl -s "${ES_HOST}")
        if [ -n "$RESPONSE" ]; then
            ES_VERSION=$(echo "$RESPONSE" | jq -r '.version.number')
            if [[ -n "$ES_VERSION" && "$ES_VERSION" != "null" ]]; then
                success "检测到Elasticsearch版本: $ES_VERSION"
                # 如果无认证访问成功，说明ES未启用安全认证
                ES_USER=""
                ES_PASSWORD=""
                return
            fi
        fi

        if [ $i -lt 6 ]; then
            info "等待Elasticsearch服务响应中... 再等待5秒"
            sleep 5
        fi
    done

    error "无法获取Elasticsearch版本。请检查："
    error "1. ES服务是否正在运行"
    error "2. ES服务是否可访问 (${ES_HOST})"
    error "3. 认证信息是否正确 (用户名: ${ES_USER})"
    error "4. 网络连接是否正常"
    exit 1
}

# 检查Kibana是否已安装
check_kibana_installed() {
    info "检查Kibana是否已安装..."
    
    if dpkg -l | grep -q kibana; then
        KIBANA_INSTALLED=true
        KIBANA_VERSION=$(dpkg -l | grep kibana | awk '{print $3}' | cut -d'-' -f1)
        success "检测到已安装的Kibana版本: $KIBANA_VERSION"
    else
        KIBANA_INSTALLED=false
        info "未检测到已安装的Kibana"
    fi
}

# 安装Kibana
install_kibana() {
    if [ "$KIBANA_INSTALLED" = true ]; then
        # 检查版本是否匹配
        if [[ "$KIBANA_VERSION" == "$ES_VERSION"* ]]; then
            success "Kibana版本与Elasticsearch版本匹配"
            return
        else
            warning "Kibana版本($KIBANA_VERSION)与Elasticsearch版本($ES_VERSION)不匹配，将重新安装"
            apt-get remove -y kibana
        fi
    fi
    
    info "开始安装Kibana $ES_VERSION..."
    
    # 下载Kibana
    TEMP_DEB="/tmp/kibana-$ES_VERSION-amd64.deb"
    KIBANA_URL="https://artifacts.elastic.co/downloads/kibana/kibana-$ES_VERSION-amd64.deb"
    
    info "下载Kibana $ES_VERSION..."
    info "下载地址: $KIBANA_URL"
    
    # 使用wget下载并显示进度
    if command -v wget &> /dev/null; then
        if wget --progress=bar:force:noscroll -O "$TEMP_DEB" "$KIBANA_URL"; then
            success "Kibana下载完成"
        else
            error "Kibana下载失败"
            exit 1
        fi
    # 如果没有wget，使用curl下载并显示进度
    elif command -v curl &> /dev/null; then
        if curl -# -L -o "$TEMP_DEB" "$KIBANA_URL"; then
            success "Kibana下载完成"
        else
            error "Kibana下载失败"
            exit 1
        fi
    else
        error "未找到wget或curl命令，无法下载Kibana"
        exit 1
    fi
    
    # 显示下载文件大小
    FILE_SIZE=$(ls -lh "$TEMP_DEB" | awk '{print $5}')
    info "下载文件大小: $FILE_SIZE"
    
    # 安装Kibana
    info "安装Kibana包..."
    if dpkg -i "$TEMP_DEB"; then
        success "Kibana安装完成"
    else
        error "Kibana安装失败"
        exit 1
    fi
    
    # 清理临时文件
    rm -f "$TEMP_DEB"
}

# 启动Kibana服务
start_kibana() {
    info "启动Kibana服务..."
    systemctl restart kibana
    sleep 5
    
    # 检查Kibana服务状态
    if systemctl is-active --quiet kibana; then
        success "Kibana服务已成功启动"
    else
        error "Kibana服务启动失败，检查日志以获取更多信息"
        journalctl -u kibana --no-pager -n 20
        exit 1
    fi
}

# 检查Kibana是否正常运行
check_kibana_running() {
    info "检查Kibana是否正常运行..."
    
    # 等待Kibana完全启动
    info "等待Kibana完全启动（最多等待60秒）..."
    for i in {1..12}; do
        if [ -n "$ES_USER" ] && [ -n "$ES_PASSWORD" ]; then
            if curl -s -u "${ES_USER}:${ES_PASSWORD}" http://localhost:5601/api/status | grep -q "kibana"; then
                success "Kibana已成功运行"
                break
            fi
        else
            if curl -s http://localhost:5601/api/status | grep -q "kibana"; then
                success "Kibana已成功运行"
                break
            fi
        fi
        
        if [ $i -eq 12 ]; then
            warning "Kibana启动时间超过预期，但将继续检查"
        else
            info "Kibana仍在启动中，再等待5秒..."
            sleep 5
        fi
    done
    
    # 获取本机IP地址
    SERVER_IP=$(hostname -I | awk '{print $1}')
    
    # 检查端口是否正在监听
    if netstat -tulpn | grep -q ":5601"; then
        success "Kibana正在监听5601端口"
        
        # 检查是否绑定到0.0.0.0
        if netstat -tulpn | grep -q "0.0.0.0:5601"; then
            success "Kibana已配置为接受所有IP的连接"
        else
            warning "Kibana可能没有配置为接受所有IP的连接，请检查配置"
        fi
    else
        error "Kibana没有监听5601端口，服务可能没有正常运行"
        exit 1
    fi
}

# 显示访问信息
show_access_info() {
    SERVER_IP=$(hostname -I | awk '{print $1}')
    
    echo -e "\n${GREEN}=====================================${NC}"
    echo -e "${GREEN}      Kibana 安装和配置完成!      ${NC}"
    echo -e "${GREEN}=====================================${NC}"
    echo -e "您可以通过以下地址访问Kibana:"
    echo -e "${BLUE}http://$SERVER_IP:${KIBANA_PORT}${NC}"
    
    if [ -n "$ES_USER" ] && [ -n "$ES_PASSWORD" ]; then
        echo -e "\n认证信息:"
        echo -e "用户名: ${YELLOW}${ES_USER}${NC}"
        echo -e "密码: ${YELLOW}${ES_PASSWORD}${NC}"
    fi
    
    echo -e "\n如果无法访问，请检查:"
    echo -e "1. 防火墙设置 - 确保允许${KIBANA_PORT}端口的访问"
    echo -e "   命令: ${YELLOW}sudo ufw allow ${KIBANA_PORT}/tcp${NC} (如果使用ufw)"
    echo -e "2. 云服务器安全组 - 开放${KIBANA_PORT}端口"
    echo -e "3. 网络连接 - 确保客户端可以ping通服务器"
    echo -e "\n常用命令:"
    echo -e "- 启动Kibana: ${YELLOW}sudo systemctl start kibana${NC}"
    echo -e "- 停止Kibana: ${YELLOW}sudo systemctl stop kibana${NC}"
    echo -e "- 重启Kibana: ${YELLOW}sudo systemctl restart kibana${NC}"
    echo -e "- 查看Kibana状态: ${YELLOW}sudo systemctl status kibana${NC}"
    echo -e "- 查看Kibana日志: ${YELLOW}sudo journalctl -u kibana${NC}"
    echo -e "${GREEN}=====================================${NC}\n"
}

# 主流程
main() {
    info "开始Kibana一键安装部署脚本..."

    # 安装依赖
    install_dependencies
    
    # 检查ES版本
    check_es_version
    
    # 获取ES认证信息
    get_es_credentials
    
    # 如果ES未启用安全认证，初始化安全认证
    if [ -z "$ES_USER" ] || [ -z "$ES_PASSWORD" ]; then
        init_es_security
    fi
    
    # 检查Kibana是否已安装
    check_kibana_installed
    
    # 安装Kibana
    install_kibana
    
    # 配置Kibana远程访问
    configure_kibana_remote
    
    # 配置防火墙
    configure_firewall
    
    # 启动Kibana服务
    start_kibana
    
    # 检查Kibana是否正常运行
    check_kibana_running
    
    # 显示访问信息
    show_access_info
}

# 执行主流程
main 