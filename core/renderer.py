import xml.etree.ElementTree as ET
import csv
import os
# 从同级目录的 color_utils.py 导入颜色算法函数
from .color_utils import get_color_intensity, boost_saturation

def add_top_legend(root, party_colors, party_seats, custom_title, stroke_width=1.0):
    """
    [纯函数] 在地图顶部绘制图例
    参数:
      root: SVG的根节点对象
      party_colors: 政党颜色字典
      party_seats: 政党席位字典
      custom_title: 标题文字
      stroke_width: 描边宽度 (用于图例中的示意图)
    """
    # 1. 获取尺寸
    viewbox = root.get('viewBox')
    if not viewbox:
        w = float(root.get('width', '1000').replace('px',''))
        h = float(root.get('height', '1000').replace('px',''))
        viewbox = f"0 0 {w} {h}"
        
    vb_parts = [float(x) for x in viewbox.split()]
    min_x, min_y, width, height = vb_parts
    
    # 增加图例区域高度
    legend_height = 200 
    
    # 扩展 viewBox
    new_min_y = min_y - legend_height
    new_height = height + legend_height
    root.set('viewBox', f"{min_x} {new_min_y} {width} {new_height}")
    
    # 创建图例组
    legend_group = ET.SubElement(root, 'g', id='_Legend_Layer')
    
    # A. 背景
    bg = ET.SubElement(legend_group, 'rect')
    bg.set('x', str(min_x))
    bg.set('y', str(new_min_y))
    bg.set('width', str(width))
    bg.set('height', str(legend_height))
    bg.set('style', "fill:#FFFFFF; stroke:none;")

    # B. 标题
    title_y = new_min_y + 180
    title_node = ET.SubElement(legend_group, 'text')
    title_node.text = custom_title
    title_node.set('x', str(min_x + width / 2))
    title_node.set('y', str(title_y))
    title_node.set('style', "font-size:64px; font-family:sans-serif; font-weight:bold; text-anchor:middle; fill:#000000;")

    if not party_colors: return

    # C. 绘制垂直色阶柱状图
    num_parties = len(party_colors)
    col_width = 60   
    gap_width = 25   
    ratios = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8] 
    step_height = 30 
    
    # 计算布局
    total_legend_width = num_parties * col_width + (num_parties - 1) * gap_width
    right_margin = 100
    start_x = min_x + width - total_legend_width - right_margin
    
    # 柱状图底部 Y
    bar_bottom_y = new_min_y + legend_height + 200 

    # 1. 绘制左侧刻度
    scale_x = start_x - 15 
    for j, ratio in enumerate(ratios):
        rect_y = bar_bottom_y - (j + 1) * step_height - (step_height/2) + 8
        label = ET.SubElement(legend_group, 'text')
        label.text = f"{int(ratio*100)}%"
        label.set('x', str(scale_x))
        label.set('y', str(rect_y))
        label.set('style', "font-size:20px; font-family:sans-serif; text-anchor:end; fill:#666666; font-weight:bold;")

    # 2. 遍历政党
    for i, (p_name, p_color) in enumerate(party_colors.items()):
        current_x = start_x + i * (col_width + gap_width)
        text_center_x = current_x + col_width/2
        
        # 2.1 色阶块
        for j, ratio in enumerate(ratios):
            # 注意：这里直接调用导入的函数，不需要 self.
            fill_color = get_color_intensity(p_color, ratio)
            rect_y = bar_bottom_y - (j + 1) * step_height
            
            block = ET.SubElement(legend_group, 'rect')
            block.set('x', str(current_x))
            block.set('y', str(rect_y))
            block.set('width', str(col_width))
            block.set('height', str(step_height))
            block.set('style', f"fill:{fill_color}; stroke:#FFFFFF; stroke-width:1;")

        # 2.2 底部原色条
        bar_base = ET.SubElement(legend_group, 'rect')
        bar_base.set('x', str(current_x))
        bar_base.set('y', str(bar_bottom_y + 5))
        bar_base.set('width', str(col_width))
        bar_base.set('height', str(8))
        
        # 注意：这里直接调用导入的函数
        pure_rgb = boost_saturation(p_color)
        pure_hex = f"#{pure_rgb[0]:02x}{pure_rgb[1]:02x}{pure_rgb[2]:02x}"
        bar_base.set('style', f"fill:{pure_hex}; stroke:none;")

        # 2.3 底部党名 (自动换行)
        name_text = ET.SubElement(legend_group, 'text')
        text_y = bar_bottom_y + 40 
        
        name_text.set('x', str(text_center_x))
        name_text.set('y', str(text_y))
        name_text.set('style', "font-size:24px; font-family:sans-serif; font-weight:bold; text-anchor:middle; fill:#000000;")
        
        chars_per_line = 3 
        lines = [p_name[j:j+chars_per_line] for j in range(0, len(p_name), chars_per_line)]
        
        last_line_y_offset = 0
        for index, line in enumerate(lines):
            tspan = ET.SubElement(name_text, 'tspan')
            tspan.text = line
            tspan.set('x', str(text_center_x)) 
            if index == 0:
                tspan.set('dy', '0') 
            else:
                tspan.set('dy', '1.2em') 
            last_line_y_offset = index * 1.2 * 24

        # 2.4 底部席位数字
        seats = party_seats.get(p_name, 0)
        
        seat_text = ET.SubElement(legend_group, 'text')
        seat_text.text = str(seats)
        seat_text.set('x', str(text_center_x))
        seat_text.set('y', str(text_y + last_line_y_offset + 35)) 
        seat_text.set('style', f"font-size:32px; font-family:sans-serif; font-weight:bold; text-anchor:middle; fill:{pure_hex};")


def render_map_from_data(svg_path, output_path, district_data, party_colors, party_seats, map_title, stroke_width_str="1.0"):
    """
    [纯函数] 接收处理好的数据字典，渲染SVG并保存
    不再负责读取CSV文件，只负责画图
    """
    if not os.path.exists(svg_path):
        return False, "SVG 模板文件不存在"

    try:
        # 处理描边宽度参数
        try:
            base_stroke_width = float(stroke_width_str)
        except:
            base_stroke_width = 1.0
            
        district_stroke = base_stroke_width
        province_stroke = base_stroke_width + 1.5 
        if province_stroke < 1.0: province_stroke = 1.5 

        # === SVG 渲染 ===
        ET.register_namespace("", "http://www.w3.org/2000/svg")
        tree = ET.parse(svg_path)
        root = tree.getroot()
        parent_map = {c: p for p in tree.iter() for c in p}
        
        matches = 0
        
        for element in root.iter():
            tag = element.tag.split('}')[-1]
            if tag == 'path':
                d_id = element.get('id', '')
                parent = parent_map.get(element)
                p_id = parent.get('id', '') if parent is not None else ''
                p_name = parent.get('data-name', '') if parent is not None else ''
                
                # A. 空白省份 (白底黑边)
                if "空白" in p_id or "空白" in p_name:
                    style = f"fill:#FFFFFF; stroke:#000000; stroke-width:{province_stroke}; stroke-linejoin:round;"
                    element.set('style', style)
                    
                # B. 选区 (填色)
                elif '-' in d_id:
                    data = district_data.get(d_id)
                    if data:
                        fill_color = data['color']
                        rate_percent = f"{int(data['rate'] * 100)}%"
                        
                        # === 埋入数据给前端 JS 使用 ===
                        element.set('data-rate', rate_percent)
                        if 'winner_name' in data:
                            element.set('data-party', data['winner_name'])
                        
                        style = f"fill:{fill_color}; stroke:#FFFFFF; stroke-width:{district_stroke}; stroke-linejoin:round;"
                        element.set('style', style)
                        matches += 1
                    else:
                        # 无数据区域，默认填充灰白
                        style = f"fill:#f0f0f0; stroke:#FFFFFF; stroke-width:{district_stroke}; stroke-linejoin:round;"
                        element.set('style', style)
                    
                # C. 省界 (透底黑边)
                elif d_id:
                    style = f"fill:none; stroke:#000000; stroke-width:{province_stroke}; stroke-linejoin:round; stroke-linecap:round;"
                    element.set('style', style)

        # === 添加图例 ===
        add_top_legend(root, party_colors, party_seats, map_title, district_stroke)
        
        # === 保存 ===
        tree.write(output_path)
        
        return True, f"成功渲染 {matches} 个选区"

    except Exception as e:
        import traceback
        traceback.print_exc()
        return False, str(e)