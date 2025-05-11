from fontTools.ttLib import TTFont
import os

def convert_to_woff_with_fonttools(input_path, output_path):
    """使用 fonttools 将 OTF/TTF 转换为 WOFF。"""
    try:
        font = TTFont(input_path)
        font.flavor = "woff"
        font.save(output_path)
        print(f"成功转换 (fonttools): {input_path} -> {output_path}")
    except Exception as e:
        print(f"转换失败 (fonttools): {input_path} -> {output_path}")
        print(f"错误信息: {e}")

def convert_folder_fonts_fonttools(folder_path):
    """转换指定文件夹中所有非 WOFF 字体文件 (使用 fonttools)。"""
    for filename in os.listdir(folder_path):
        if filename.lower().endswith(('.otf', '.ttf')):
            input_file = os.path.join(folder_path, filename)
            output_file = os.path.join(folder_path, os.path.splitext(filename)[0] + '.woff')
            if not os.path.exists(output_file):
                convert_to_woff_with_fonttools(input_file, output_file)
            else:
                print(f"跳过已存在的 WOFF 文件: {output_file}")

if __name__ == "__main__":
    target_folder = r"F:\desktop\hiiragi\font"
    if os.path.isdir(target_folder):
        convert_folder_fonts_fonttools(target_folder)
        print("转换完成。")
    else:
        print("错误: 指定的文件夹路径不存在。")