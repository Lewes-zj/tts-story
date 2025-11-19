import json
import os
import sys


class TestJsonReader:
    """独立的测试JSON读取器，用于读取test.json文件并将其内容存储在列表中"""

    def __init__(self, json_file_path):
        """
        初始化TestJsonReader

        Args:
            json_file_path (str): JSON文件的路径
        """
        self.json_file_path = json_file_path
        self.data_list = []

    def read_json_to_list(self):
        """
        读取JSON文件并将内容存储在列表中

        Returns:
            list: 包含JSON数据的列表
        """
        try:
            # 检查文件是否存在
            if not os.path.exists(self.json_file_path):
                raise FileNotFoundError(f"文件未找到: {self.json_file_path}")

            # 读取JSON文件
            with open(self.json_file_path, 'r', encoding='utf-8') as file:
                data = json.load(file)

            # 确保数据是一个列表
            if isinstance(data, list):
                self.data_list = data
            else:
                # 如果数据不是列表，将其包装在列表中
                self.data_list = [data]

            return self.data_list

        except json.JSONDecodeError as e:
            print(f"JSON解析错误: {e}")
            return []
        except Exception as e:
            print(f"读取文件时发生错误: {e}")
            return []

    def display_data(self):
        """显示读取的数据"""
        if not self.data_list:
            print("没有数据可显示")
            return

        print(f"总共读取到 {len(self.data_list)} 条记录:")
        for i, item in enumerate(self.data_list):
            print(f"\n记录 {i+1}:")
            for key, value in item.items():
                print(f"  {key}: {value}")

    def get_data_list(self):
        """
        获取数据列表

        Returns:
            list: 包含JSON数据的列表
        """
        return self.data_list

    def get_record_count(self):
        """
        获取记录数量

        Returns:
            int: 记录数量
        """
        return len(self.data_list)


def main():
    """主函数，演示如何使用TestJsonReader类"""
    # 检查是否提供了文件路径参数
    if len(sys.argv) < 2:
        print("使用方法: python test_json_reader.py <json文件路径>")
        sys.exit(1)
    
    # 获取命令行参数中的JSON文件路径
    json_file_path = sys.argv[1]
    
    # 检查文件是否存在
    if not os.path.exists(json_file_path):
        print(f"错误: 文件 '{json_file_path}' 不存在")
        sys.exit(1)
    
    # 创建TestJsonReader实例
    reader = TestJsonReader(json_file_path)

    # 读取JSON数据到列表
    data = reader.read_json_to_list()

    # 显示数据
    reader.display_data()

    # 显示记录数量
    print(f"\n记录总数: {reader.get_record_count()}")


if __name__ == "__main__":
    main()
