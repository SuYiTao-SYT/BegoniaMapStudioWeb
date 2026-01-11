import xml.etree.ElementTree as ET
import os

def clean_and_extract_ids(input_svg_path, output_svg_path):
    """
    清洗SVG，修复Polygon，提取选区ID
    返回: (成功与否, 提取到的选区列表)
    """
    if not os.path.exists(input_svg_path):
        return False, []
        
    try:
        ET.register_namespace("", "http://www.w3.org/2000/svg")
        tree = ET.parse(input_svg_path)
        root = tree.getroot()
        
        extracted_ids = []
        
        # 内部递归函数
        def process_element(element, parent_id="Root"):
            current_id = element.get('id', '')
            is_district = '-' in current_id
            tag_name = element.tag.split('}')[-1].lower()
            
            if tag_name in ['polygon', 'polyline']:
                points = element.get('points')
                if points:
                    new_elem = ET.Element(element.tag.replace(tag_name, 'path'))
                    if is_district or tag_name == 'polygon':
                        path_data = f"M {points} Z"
                    else:
                        path_data = f"M {points}"
                    
                    new_elem.set('d', path_data)
                    for k, v in element.attrib.items():
                        if k not in ['points', 'd']:
                            new_elem.set(k, v)
                    
                    element.tag = new_elem.tag
                    element.attrib = new_elem.attrib
                    tag_name = 'path' # 更新标签名

            if tag_name == 'path' and is_district:
                extracted_ids.append({'parent': parent_id, 'id': current_id})
            
            next_parent = current_id if element.tag.endswith('g') and current_id else parent_id
            if element.get('data-name'):
                next_parent = element.get('data-name')

            for child in element:
                process_element(child, next_parent)

        process_element(root)
        tree.write(output_svg_path)
        
        return True, extracted_ids

    except Exception as e:
        print(f"Error processing SVG: {e}")
        return False, []