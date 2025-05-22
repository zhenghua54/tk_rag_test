#!/bin/bash
set -e

echo "==> 创建 socket 和 pid 文件目录..."
sudo mkdir -p /var/run/mysqld
sudo chown mysql:mysql /var/run/mysqld

echo "==> 确保数据目录存在并权限正确..."
sudo chown -R mysql:mysql /var/lib/mysql

echo "==> 强制设置标准 socket 路径..."
MYSQL_CNF="/etc/mysql/mysql.conf.d/mysqld.cnf"
sudo sed -i '/^socket/d' "$MYSQL_CNF"
sudo sed -i '/^\[mysqld\]/a socket=/var/run/mysqld/mysqld.sock\npid-file=/var/run/mysqld/mysqld.pid' "$MYSQL_CNF"

echo "==> 尝试重启 MySQL 服务..."
sudo systemctl restart mysql || {
    echo "❌ MySQL 重启失败，正在打印错误日志："
    sudo journalctl -xeu mysql.service | tail -n 50
    exit 1
}

echo "✅ MySQL 启动成功，验证 socket："
sudo ls -l /var/run/mysqld/mysqld.sock

echo "==> 测试 root 用户连接..."
sudo mysql -u root || {
    echo "❌ 无法连接 root 用户，请尝试通过 socket 明确路径连接并修复密码："
    TMP_SOCK=$(find /tmp -name 'mysqld.sock' 2>/dev/null | head -n 1)
    if [[ -n "$TMP_SOCK" ]]; then
        echo "🛠 发现临时 socket 文件: $TMP_SOCK"
        echo "请手动执行以下命令修复 root 密码："
        echo "sudo mysql --socket=$TMP_SOCK -u root"
        echo "然后在 mysql 控制台中执行："
        echo "ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY 'your_secure_password';"
        echo "FLUSH PRIVILEGES;"
    else
        echo "未找到临时 socket，需进一步排查日志。"
    fi
}