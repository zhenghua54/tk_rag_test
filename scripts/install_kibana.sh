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

# 检查当前安装的ES版本
check_es_version() {
    info "检查当前安装的Elasticsearch版本..."
    
    if ! command -v curl &> /dev/null; then
        info "安装curl..."
        apt-get update && apt-get install -y curl
    fi
    
    ES_VERSION=$(curl -s http://localhost:9200 | grep number | cut -d '"' -f 4)
    
    if [ -z "$ES_VERSION" ]; then
        error "无法获取Elasticsearch版本。请确保Elasticsearch正在运行且可以通过 http://localhost:9200 访问。"
        exit 1
    else
        success "检测到Elasticsearch版本: $ES_VERSION"
    fi
}

# 检查Kibana是否已安装
check_kibana_installed() {
    if dpkg -l | grep -q kibana; then
        warning "检测到Kibana已安装，将跳过安装步骤"
        KIBANA_INSTALLED=true
        KIBANA_VERSION=$(dpkg -l | grep kibana | awk '{print $3}')
        success "当前安装的Kibana版本: $KIBANA_VERSION"
    else
        KIBANA_INSTALLED=false
        info "未检测到Kibana，将进行安装"
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
    info "下载Kibana $ES_VERSION..."
    
    if wget -q -O "$TEMP_DEB" "https://artifacts.elastic.co/downloads/kibana/kibana-$ES_VERSION-amd64.deb"; then
        success "Kibana下载完成"
    else
        error "Kibana下载失败"
        exit 1
    fi
    
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

# 配置Kibana
configure_kibana() {
    info "配置Kibana..."
    
    # 备份原始配置文件
    if [ -f /etc/kibana/kibana.yml ]; then
        cp /etc/kibana/kibana.yml /etc/kibana/kibana.yml.bak
        success "已备份原始配置文件到 /etc/kibana/kibana.yml.bak"
    fi
    
    # 创建新配置文件
    cat > /etc/kibana/kibana.yml <<EOF
# Kibana配置文件
# 监听端口
server.port: 5601

# 允许从所有IP访问Kibana
server.host: "0.0.0.0"

# Elasticsearch连接设置
elasticsearch.hosts: ["http://localhost:9200"]

# 日志设置
logging.dest: /var/log/kibana/kibana.log

# 其他设置可以根据需要添加
EOF
    
    success "Kibana配置文件已更新"
    
    # 创建日志目录
    mkdir -p /var/log/kibana
    chown -R kibana:kibana /var/log/kibana
    
    # 确保Kibana服务自启动
    systemctl daemon-reload
    systemctl enable kibana
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
        if curl -s http://localhost:5601/api/status | grep -q "kibana"; then
            success "Kibana已成功运行"
            break
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
    echo -e "${BLUE}http://$SERVER_IP:5601${NC}"
    echo -e "\n如果无法访问，请检查:"
    echo -e "1. 防火墙设置 - 确保允许5601端口的访问"
    echo -e "   命令: ${YELLOW}sudo ufw allow 5601/tcp${NC} (如果使用ufw)"
    echo -e "2. 云服务器安全组 - 开放5601端口"
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
    
    # 检查ES版本
    check_es_version
    
    # 检查Kibana是否已安装
    check_kibana_installed
    
    # 安装Kibana
    install_kibana
    
    # 配置Kibana
    configure_kibana
    
    # 启动Kibana服务
    start_kibana
    
    # 检查Kibana是否正常运行
    check_kibana_running
    
    # 显示访问信息
    show_access_info
}

# 执行主流程
main 