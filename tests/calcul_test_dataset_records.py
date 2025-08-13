import os
import pandas as pd
from pathlib import Path

# 统计每个数据集的test分割有多少记录

base_dir = Path("/home/zh/gitClone/tk_rag/data/ragbench")
datasets = [
    "covidqa", "delucionqa", "expertqa", "hagrid",
    "msmarco", "techqa", "cuad", "emanual",
    "finqa", "hotpotqa", "pubmedqa", "tatqa"
]

def count_test_records(dataset_name: str) -> dict:
    """
    统计指定数据集的test分割记录数
    
    Args:
        dataset_name: 数据集名称
        
    Returns:
        dict: 包含记录数统计的字典
    """
    dataset_dir = base_dir / dataset_name
    if not dataset_dir.exists():
        return {"dataset": dataset_name, "status": "路径不存在", "records": 0}
    
    # 查找test分割文件
    test_files = []
    for file in os.listdir(dataset_dir):
        if file.startswith("test") and file.endswith(".parquet"):
            test_files.append(file)
    
    if not test_files:
        return {"dataset": dataset_name, "status": "未找到test文件", "records": 0}
    
    total_records = 0
    file_records = {}
    
    for file in test_files:
        path = dataset_dir / file
        try:
            df = pd.read_parquet(path)
            records_count = len(df)
            total_records += records_count
            file_records[file] = records_count
            print(f"  - {file}: {records_count} 条记录")
        except Exception as e:
            print(f"  - {file}: 读取失败 - {e}")
            file_records[file] = 0
    
    return {
        "dataset": dataset_name,
        "status": "成功",
        "records": total_records,
        "files": file_records
    }

def main():
    """主函数"""
    print("=" * 60)
    print("RagBench数据集Test分割记录数统计")
    print("=" * 60)
    
    results = []
    total_records = 0
    
    for dataset in datasets:
        print(f"\n处理数据集: {dataset}")
        result = count_test_records(dataset)
        results.append(result)
        
        if result["status"] == "成功":
            total_records += result["records"]
            print(f"  ✓ {dataset}: {result['records']} 条记录")
        else:
            print(f"  ✗ {dataset}: {result['status']}")
    
    # 输出汇总结果
    print("\n" + "=" * 60)
    print("汇总结果")
    print("=" * 60)
    
    successful_datasets = [r for r in results if r["status"] == "成功"]
    failed_datasets = [r for r in results if r["status"] != "成功"]
    
    print(f"成功处理的数据集: {len(successful_datasets)}/{len(datasets)}")
    print(f"总记录数: {total_records:,} 条")
    
    if successful_datasets:
        print("\n详细统计:")
        print("-" * 40)
        for result in sorted(successful_datasets, key=lambda x: x["records"], reverse=True):
            print(f"{result['dataset']:12}: {result['records']:6,} 条记录")
    
    if failed_datasets:
        print("\n处理失败的数据集:")
        print("-" * 40)
        for result in failed_datasets:
            print(f"{result['dataset']:12}: {result['status']}")
    
    # 保存结果到文件
    output_file = Path("test_dataset_records_summary.txt")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("RagBench数据集Test分割记录数统计\n")
        f.write("=" * 50 + "\n")
        f.write(f"统计时间: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"总记录数: {total_records:,} 条\n\n")
        
        f.write("详细统计:\n")
        f.write("-" * 30 + "\n")
        for result in sorted(successful_datasets, key=lambda x: x["records"], reverse=True):
            f.write(f"{result['dataset']:12}: {result['records']:6,} 条记录\n")
        
        if failed_datasets:
            f.write("\n处理失败的数据集:\n")
            f.write("-" * 30 + "\n")
            for result in failed_datasets:
                f.write(f"{result['dataset']:12}: {result['status']}\n")
    
    print(f"\n结果已保存到: {output_file}")
    print("=" * 60)

if __name__ == "__main__":
    main()
