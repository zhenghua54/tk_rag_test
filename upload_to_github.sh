
#!/bin/bash

# 设置远程仓库地址
REPO_URL="https://github.com/zhenghua54/tk_rag_test.git"
BRANCH_NAME="main"

# 检查是否在 Git 仓库中
if [ ! -d ".git" ]; then
  echo "当前目录不是 Git 仓库，正在初始化..."
  git init
fi

# 添加所有文件
echo "添加所有更改..."
git add .

# 设置提交信息（使用当前时间）
COMMIT_MSG="Upload at $(date '+%Y-%m-%d %H:%M:%S')"
git commit -m "$COMMIT_MSG"

# 设置主分支名（如未设置）
git branch -M $BRANCH_NAME

# 添加远程地址（如果已经添加则跳过）
if ! git remote | grep -q "origin"; then
  echo "添加远程仓库 origin -> $REPO_URL"
  git remote add origin "$REPO_URL"
else
  echo "远程仓库已存在，跳过添加"
fi

# 推送到远程仓库
echo "推送到远程仓库..."
git push -u origin $BRANCH_NAME

echo "✅ 上传完成！"
