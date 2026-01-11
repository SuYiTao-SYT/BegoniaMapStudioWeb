import colorsys

def boost_saturation(hex_color):
    """将任意颜色转换为高饱和度、高亮度的版本"""
    hex_color = hex_color.lstrip('#')
    if len(hex_color) != 6: return (128, 128, 128)
    
    r = int(hex_color[0:2], 16) / 255.0
    g = int(hex_color[2:4], 16) / 255.0
    b = int(hex_color[4:6], 16) / 255.0
    
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    
    # 强制提升饱和度和亮度
    target_s = max(s, 0.8) 
    target_v = max(v, 0.9)
    
    new_r, new_g, new_b = colorsys.hsv_to_rgb(h, target_s, target_v)
    return int(new_r * 255), int(new_g * 255), int(new_b * 255)

def get_color_intensity(hex_color, ratio):
    """根据得票率混合白色"""
    base_r, base_g, base_b = boost_saturation(hex_color)
    
    min_threshold = 0.25
    max_threshold = 0.70
    
    if ratio >= max_threshold:
        strength = 1.0
    elif ratio <= min_threshold:
        strength = 0.15 
    else:
        strength = 0.15 + 0.85 * (ratio - min_threshold) / (max_threshold - min_threshold)

    final_r = int(base_r * strength + 255 * (1 - strength))
    final_g = int(base_g * strength + 255 * (1 - strength))
    final_b = int(base_b * strength + 255 * (1 - strength))
    
    return f"#{final_r:02x}{final_g:02x}{final_b:02x}"