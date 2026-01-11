import csv
import os
import shutil
import json # 如果以后要存配置可以用json，暂时用csv

class DataManager:
    def __init__(self, workspace_path):
        self.workspace = workspace_path
        self.files = {
            'districts': os.path.join(workspace_path, 'districts.csv'),
            'parties': os.path.join(workspace_path, 'parties.csv'),
            'votes': os.path.join(workspace_path, 'votes.csv')
        }
        
    def init_workspace(self):
        """初始化空的工作区文件"""
        if not os.path.exists(self.workspace):
            os.makedirs(self.workspace)
            
        # 如果文件不存在，创建带表头的空文件
        if not os.path.exists(self.files['parties']):
            with open(self.files['parties'], 'w', encoding='utf-8-sig', newline='') as f:
                csv.writer(f).writerow(['Party_ID', 'Name_CN', 'Color', 'Alliance'])
                
        if not os.path.exists(self.files['districts']):
            with open(self.files['districts'], 'w', encoding='utf-8-sig', newline='') as f:
                csv.writer(f).writerow(['District_ID', 'Province_ID', 'Name', 'Type', 'Seats'])

    def import_from_legacy_v2(self, legacy_csv_path):
        """
        [核心功能] 将 v2.5 的单一大表拆解为 v3.0 的三张表
        """
        self.init_workspace()
        
        parties = []
        districts = []
        votes_data = []
        
        with open(legacy_csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            rows = list(reader)
            
            # 1. 解析 META 行 -> 生成 Parties 表
            meta_row = rows[0]
            party_names_ordered = [] # 记录列顺序
            
            for item in meta_row[1:]:
                if ':' in item:
                    p_name, p_color = item.split(':')
                    p_name = p_name.strip()
                    # 自动生成一个简短ID (比如 P01, P02) 或者直接用名字
                    p_id = f"P_{len(parties)+1:02d}" 
                    parties.append([p_id, p_name, p_color.strip(), "Default"])
                    party_names_ordered.append(p_id)

            # 2. 解析数据行 -> 生成 Districts 和 Votes 表
            header = rows[1]
            # 假设 header 是 [Prov_ID, Dist_ID, PartyA, PartyB...]
            
            for row in rows[2:]:
                if len(row) < 3: continue
                prov_id = row[0]
                dist_id = row[1]
                
                # 存入 Districts 表 (默认设为小选区 FPTP, 1席)
                districts.append([dist_id, prov_id, dist_id, 'FPTP', 1])
                
                # 存入 Votes 表
                # 我们这里把宽表转为长表存储吗？为了方便Excel编辑，
                # 其实 v3.0 的 votes.csv 也可以保持宽表格式，只要表头动态匹配即可。
                # 这里为了简单，我们先把原始投票数据存进去，表头用 Party_ID
                vote_nums = row[2:]
                votes_data.append([dist_id] + vote_nums)

        # === 3. 写入硬盘 ===
        
        # 写 Parties
        with open(self.files['parties'], 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.writer(f)
            w.writerow(['Party_ID', 'Name_CN', 'Color', 'Alliance'])
            w.writerows(parties)
            
        # 写 Districts
        with open(self.files['districts'], 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.writer(f)
            w.writerow(['District_ID', 'Province_ID', 'Name', 'Type', 'Seats'])
            w.writerows(districts)
            
        # 写 Votes (保持宽表结构，方便Excel编辑)
        with open(self.files['votes'], 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.writer(f)
            # 表头：选区ID + 各个政党ID
            w.writerow(['District_ID'] + party_names_ordered)
            w.writerows(votes_data)
            
        return True, "成功将旧版数据升级为 v3.0 数据库格式"

    def get_joined_data(self):
        """
        [给渲染器用] 读取三张表，在内存中拼合成渲染器需要的数据格式
        返回: 
        - district_data: { 'XJ-1': {'color': '#xxx', 'rate': 0.55, 'winner_name': 'LDP'} }
        - party_colors: {'LDP': '#3366CC', ...}
        - party_seats: {'LDP': 10, ...}
        """
        # 1. 读取政党信息 (Parties)
        party_colors = {}
        party_names = {} # ID -> Name
        with open(self.files['parties'], 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                pid = row['Party_ID']
                party_colors[row['Name_CN']] = row['Color']
                party_names[pid] = row['Name_CN'] # 建立 ID 到名字的映射

        # 2. 读取选情数据 (Votes)
        district_data = {}
        party_seats = {name: 0 for name in party_colors.keys()} # 初始化席位

        # 需要在这里导入颜色计算函数，避免循环引用可以放在函数内或者移动utils
        from .color_utils import get_color_intensity

        with open(self.files['votes'], 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            # 获取所有政党ID列（排除District_ID）
            party_ids = [field for field in reader.fieldnames if field != 'District_ID']
            
            for row in reader:
                d_id = row['District_ID']
                
                # 找出票数最高的
                max_votes = -1
                winner_pid = None
                total_votes = 0
                
                valid_row = True
                for pid in party_ids:
                    try:
                        votes = int(row[pid])
                        total_votes += votes
                        if votes > max_votes:
                            max_votes = votes
                            winner_pid = pid
                    except ValueError:
                        continue # 跳过非数字
                
                if total_votes > 0 and winner_pid:
                    winner_name = party_names.get(winner_pid, winner_pid)
                    base_color = party_colors.get(winner_name, "#aaaaaa")
                    
                    # 统计席位 (简单起见，假设每个区1席，如果需要支持多席位，需读取districts表)
                    if winner_name in party_seats:
                        party_seats[winner_name] += 1
                    
                    win_rate = max_votes / total_votes
                    final_color = get_color_intensity(base_color, win_rate)
                    
                    district_data[d_id] = {
                        'color': final_color,
                        'rate': win_rate,
                        'winner_name': winner_name
                    }
                else:
                    district_data[d_id] = {'color': '#ffffff', 'rate': 0, 'winner_name': 'No Data'}

        return district_data, party_colors, party_seats
    def get_district_detail(self, district_id):
        """
        [读] 获取指定选区的所有详情：基础属性 + 当前各党得票 (带政党名字)
        """
        # 0. 先把所有政党名字查出来做成字典: {'P_01': '自由党', ...}
        party_map = {}
        if os.path.exists(self.files['parties']):
            with open(self.files['parties'], 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    party_map[row['Party_ID']] = row['Name_CN']

        # 1. 找基础属性 (Districts表)
        district_info = {}
        with open(self.files['districts'], 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['District_ID'] == district_id:
                    district_info = row
                    break
        
        if not district_info:
            return None 

        # 2. 找得票数据 (Votes表)
        vote_data = [] # 改成列表，方便前端排序和显示
        
        with open(self.files['votes'], 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['District_ID'] == district_id:
                    # 遍历所有列
                    for k, v in row.items():
                        if k != 'District_ID' and v.strip().isdigit():
                            # 构造前端友好的数据结构
                            vote_data.append({
                                'id': k,                        # P_01 (用于保存)
                                'name': party_map.get(k, k),    # 自由党 (用于显示)
                                'count': int(v)                 # 票数
                            })
                    break
        
        # 可选：按票数倒序排列，让赢家在最上面
        vote_data.sort(key=lambda x: x['count'], reverse=True)

        return {
            'info': district_info,
            'votes': vote_data
        }

    def update_district_votes(self, district_id, new_votes_dict):
        """
        [写] 更新指定选区的票数
        new_votes_dict: {'LDP': 3000, 'CDP': 2000...}
        """
        # 我们需要读取整个文件，修改那一行，再写回去 (CSV的局限性，但这对于几千行来说很快)
        rows = []
        fieldnames = []
        
        # 1. 读取
        with open(self.files['votes'], 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            rows = list(reader)
            
        # 2. 修改
        updated = False
        for row in rows:
            if row['District_ID'] == district_id:
                # 更新票数
                for party_id, count in new_votes_dict.items():
                    if party_id in fieldnames:
                        row[party_id] = count
                updated = True
                break
        
        # 如果没找到（可能是新选区），以后再处理追加逻辑，先假设一定能找到
        
        # 3. 写入
        with open(self.files['votes'], 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
            
        return True