#!/bin/bash

# 1. 安装必要的依赖
echo -e "\n--------------------------------------------------------"
echo -e "正在更新系统软件包..."
sudo apt-get update
echo -e "正在安装必要的依赖：wget 和 apt-transport-https..."
sudo apt-get install -y wget apt-transport-https
echo -e "--------------------------------------------------------\n"

# 2. 检查是否已经下载过 Elasticsearch 安装包
ELASTICSEARCH_DEB="elasticsearch-7.17.14-amd64.deb"
if [ ! -f "$ELASTICSEARCH_DEB" ]; then
    echo -e "安装包不存在，开始下载 Elasticsearch 安装包..."
    wget https://artifacts.elastic.co/downloads/elasticsearch/$ELASTICSEARCH_DEB
else
    echo -e "安装包已存在，跳过下载...\n"
fi

# 3. 检查 Elasticsearch 是否已经安装
if ! dpkg -l | grep -q elasticsearch; then
    echo -e "开始安装 Elasticsearch...\n"
    sudo dpkg -i $ELASTICSEARCH_DEB
else
    echo -e "Elasticsearch 已安装，跳过安装步骤...\n"
fi

# 4. 配置 Elasticsearch
echo -e "\n--------------------------------------------------------"
echo -e "正在配置 Elasticsearch..."
sudo tee /etc/elasticsearch/elasticsearch.yml > /dev/null <<EOL
cluster.name: elasticsearch
node.name: rag_index
path.data: /var/lib/elasticsearch
path.logs: /var/log/elasticsearch
network.host: 127.0.0.1
http.port: 9200
discovery.type: single-node
EOL
echo -e "--------------------------------------------------------\n"

# 5. 配置 JVM 堆内存
echo -e "\n--------------------------------------------------------"
echo -e "正在配置 JVM 堆内存..."
sudo tee /etc/elasticsearch/jvm.options.d/heap.options > /dev/null <<EOL
-Xms2g
-Xmx2g
EOL
echo -e "--------------------------------------------------------\n"

# 6. 创建必要的目录并设置权限
echo -e "\n--------------------------------------------------------"
echo -e "正在创建 Elasticsearch 数据和日志目录，并设置权限..."
sudo mkdir -p /var/lib/elasticsearch /var/log/elasticsearch
sudo chown -R elasticsearch:elasticsearch /var/lib/elasticsearch /var/log/elasticsearch /etc/elasticsearch
sudo chmod -R 2750 /var/lib/elasticsearch /var/log/elasticsearch /etc/elasticsearch
echo -e "--------------------------------------------------------\n"

# 7. 启动 Elasticsearch 服务
if systemctl is-active --quiet elasticsearch.service; then
    echo -e "Elasticsearch 服务已启动，跳过启动步骤...\n"
else
    echo -e "正在启动 Elasticsearch 服务..."
    sudo systemctl daemon-reload
    sudo systemctl enable elasticsearch.service
    sudo systemctl start elasticsearch.service
    echo -e "正在等待 Elasticsearch 启动..."
    sleep 60
fi

# 8. 校验 Elasticsearch 服务是否启动成功
echo -e "\n--------------------------------------------------------"
echo -e "正在检查 Elasticsearch 服务是否正常启动..."
if systemctl is-active --quiet elasticsearch.service; then
    echo -e "\033[1;32mElasticsearch 服务启动成功！\033[0m"
else
    echo -e "\033[1;31mElasticsearch 服务启动失败！请检查日志以定位问题。\033[0m"
    exit 1
fi
echo -e "--------------------------------------------------------\n"

# 9. 检查 IK 插件是否已安装
echo -e "\n--------------------------------------------------------"
echo -e "正在检查 IK 插件是否已安装..."
if curl -X GET "localhost:9200/_cat/plugins?v" | grep -q "analysis-ik"; then
    echo -e "IK 分词器插件已安装，跳过安装步骤...\n"
else
    echo -e "正在安装 IK 分词器插件..."
    sudo /usr/share/elasticsearch/bin/elasticsearch-plugin install https://get.infini.cloud/elasticsearch/analysis-ik/7.17.14
    # 10. 重启 Elasticsearch 服务以激活插件
    echo -e "正在重启 Elasticsearch 服务以激活插件..."
    sudo systemctl restart elasticsearch.service
    echo -e "正在等待服务重启..."
    sleep 60
fi
echo -e "--------------------------------------------------------\n"

# 10. 校验 IK 插件是否安装成功
echo -e "\n--------------------------------------------------------"
echo -e "正在检查 IK 分词器插件是否安装成功..."
curl -X GET "localhost:9200/_cat/plugins?v" | grep "analysis-ik"
if [ $? -eq 0 ]; then
    echo -e "\033[1;32mIK 分词器插件安装成功！\033[0m"
else
    echo -e "\033[1;31mIK 分词器插件安装失败！\033[0m"
    exit 1
fi
echo -e "--------------------------------------------------------\n"

# 11. 测试 Elasticsearch 是否正常运行
echo -e "\n--------------------------------------------------------"
echo -e "正在测试 Elasticsearch 是否正常运行..."
curl -X GET "http://localhost:9200"
echo -e "--------------------------------------------------------\n"

# 12. 测试 IK 分词器是否正常工作
echo -e "\n--------------------------------------------------------"
echo -e "正在测试 IK 分词器是否正常工作..."
response=$(curl -s -X POST "http://localhost:9200/_analyze" -H 'Content-Type: application/json' -d'{"analyzer": "ik_smart","text": "中华人民共和国国歌"}')

# 检查返回的结果是否包含 "tokens" 字段，判断 IK 插件是否正常工作
if echo "$response" | grep -q '"tokens"'; then
    echo -e "\033[1;32mIK 分词器正常工作！\033[0m"
    echo -e "分词结果："
    echo "$response" | sed -n 's/.*"token":\s*"\([^"]*\)".*/\1/p'
else
    echo -e "\033[1;31mIK 分词器无法正常工作！返回错误：\033[0m"
    echo "$response"
    exit 1
fi
echo -e "--------------------------------------------------------\n"
