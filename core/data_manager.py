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
        [给渲染器用] 读取三张表，拼合数据
        逻辑更新：
        1. 席位统计基于 districts.csv 里的 Seats 值
        2. 如果 Seats == 0，则不计入席位，且地图上可能需要特殊处理
        """
        # 1. 读取政党信息
        party_colors = {}
        party_names = {}
        with open(self.files['parties'], 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                pid = row['Party_ID']
                party_colors[row['Name_CN']] = row['Color']
                party_names[pid] = row['Name_CN']

        # 2. 读取选区基础信息 (获取席位设定)
        district_meta = {} # { 'XJ-1': 1, 'XJ-2': 0 }
        with open(self.files['districts'], 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # 容错处理：确保Seats是数字
                try:
                    seats = int(row['Seats'])
                except:
                    seats = 1
                district_meta[row['District_ID']] = seats

        # 3. 读取选情数据
        district_data = {}
        party_seats = {name: 0 for name in party_colors.keys()}
        
        from .color_utils import get_color_intensity

        with open(self.files['votes'], 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            party_ids = [field for field in reader.fieldnames if field != 'District_ID']
            
            for row in reader:
                d_id = row['District_ID']
                
                # 获取该区席位数，默认为1
                seats_count = district_meta.get(d_id, 1)

                # 找出票数最高的
                max_votes = -1
                winner_pid = None
                total_votes = 0
                
                for pid in party_ids:
                    try:
                        votes = int(row[pid])
                        total_votes += votes
                        if votes > max_votes:
                            max_votes = votes
                            winner_pid = pid
                    except ValueError:
                        continue 
                
                # 只有当总票数>0 且 席位数>0 时，才算有效选举
                if total_votes > 0 and winner_pid and seats_count > 0:
                    winner_name = party_names.get(winner_pid, winner_pid)
                    base_color = party_colors.get(winner_name, "#aaaaaa")
                    
                    # === 关键修改：统计席位 ===
                    # 简单模型：该区赢家拿走该区所有席位
                    # (如果是比例代表制，这里需要更复杂的 D'Hondt 算法，目前暂按赢者通吃或单席位处理)
                    if winner_name in party_seats:
                        party_seats[winner_name] += seats_count
                    
                    win_rate = max_votes / total_votes
                    final_color = get_color_intensity(base_color, win_rate)
                    
                    district_data[d_id] = {
                        'color': final_color,
                        'rate': win_rate,
                        'winner_name': winner_name,
                        'seats': seats_count 
                    }
                else:
                    # 0席位(无改选) 或 无数据
                    district_data[d_id] = {
                        'color': '#eeeeee', # 灰色
                        'rate': 0, 
                        'winner_name': '无改选' if seats_count == 0 else 'No Data',
                        'seats': seats_count
                    }

        return district_data, party_colors, party_seats

    def update_district_data(self, district_id, new_seats, new_votes_dict):
        """
        [写 - 升级版] 同时更新席位(districts.csv)和票数(votes.csv)
        """
        # --- 1. 更新 Districts 表 (席位) ---
        dist_rows = []
        dist_fieldnames = []
        with open(self.files['districts'], 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            dist_fieldnames = reader.fieldnames
            dist_rows = list(reader)
        
        # 查找并修改
        found_dist = False
        for row in dist_rows:
            if row['District_ID'] == district_id:
                row['Seats'] = str(new_seats)
                # 既然删除了Type下拉框，这里我们可以默认保持原样，或者统一设为Custom
                found_dist = True
                break
        
        # 如果没找到(新选区)，需要追加逻辑(暂略，假设ID都存在)
        
        with open(self.files['districts'], 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=dist_fieldnames)
            writer.writeheader()
            writer.writerows(dist_rows)

        # --- 2. 更新 Votes 表 (票数) ---
        vote_rows = []
        vote_fieldnames = []
        with open(self.files['votes'], 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            vote_fieldnames = reader.fieldnames
            vote_rows = list(reader)
            
        for row in vote_rows:
            if row['District_ID'] == district_id:
                for party_id, count in new_votes_dict.items():
                    if party_id in vote_fieldnames:
                        row[party_id] = count
                break
        
        with open(self.files['votes'], 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=vote_fieldnames)
            writer.writeheader()
            writer.writerows(vote_rows)
            
        return True
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
    def batch_swing_update(self, district_ids, target_party_id, swing_percent, lock_total=True):
        """
        批量摇摆更新 (完整版)
        :param district_ids: 选区ID列表
        :param target_party_id: 目标政党ID
        :param swing_percent: 摇摆比例 (0.05 = 5%)
        :param lock_total: 是否锁定总票数
        """
        # 读取现有票数
        all_rows = []
        fieldnames = []
        
        if not os.path.exists(self.files['votes']):
            return False

        with open(self.files['votes'], 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            all_rows = list(reader)

        changed_count = 0
        
        for row in all_rows:
            # 只修改选中的选区
            if row['District_ID'] in district_ids:
                # 1. 计算该区总票数 & 读取当前各党票数
                current_votes = {} 
                total_votes = 0
                
                for k, v in row.items():
                    if k != 'District_ID' and k in fieldnames and v and v.strip().isdigit():
                        val = int(v)
                        current_votes[k] = val
                        total_votes += val
                
                if total_votes == 0: continue

                # 2. 计算变动量 (Delta)
                delta_votes = int(total_votes * swing_percent)
                
                # 获取目标政党当前票数
                target_current = current_votes.get(target_party_id, 0)
                
                # 3. 边界检查：防止减成负数
                # 预测一下修改后的票数
                final_target_votes = target_current + delta_votes
                
                if final_target_votes < 0:
                    # 如果不够扣，就扣光为止
                    delta_votes = -target_current
                
                # 如果算出来没变化（比如票数太少，乘百分比后不到1票），跳过
                if delta_votes == 0: continue

                # === 执行修改 ===
                
                # A. 更新目标政党 (无论是锁还是不锁，目标党都要变)
                row[target_party_id] = str(target_current + delta_votes)
                
                # B. 零和博弈逻辑 (如果锁定了总票数)
                if lock_total:
                    # 目标党增加了 delta，其他人就要分担 -delta
                    remaining_delta = -delta_votes
                    
                    # 找出"其他政党" (排除自己)
                    other_parties = [p for p in current_votes if p != target_party_id]
                    other_total = sum(current_votes[p] for p in other_parties)
                    
                    if other_total > 0:
                        # 按比例分摊
                        distributed_sum = 0
                        for i, p in enumerate(other_parties):
                            p_current = current_votes[p]
                            
                            # 最后一个党负责兜底(处理除不尽的余数)，保证总数严丝合缝
                            if i == len(other_parties) - 1:
                                share = remaining_delta - distributed_sum
                            else:
                                ratio = p_current / other_total
                                share = int(remaining_delta * ratio)
                                distributed_sum += share
                            
                            # 防止其他党被扣成负数 (理论上应该很少发生，但要防御)
                            new_val = p_current + share
                            if new_val < 0: new_val = 0
                            
                            row[p] = str(new_val)
                    else:
                        # 如果没有其他党可扣，那就没法锁定总票数了，只能看着它变
                        pass

                changed_count += 1

        # 写回文件
        if changed_count > 0:
            with open(self.files['votes'], 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(all_rows)
            return True
        
        return False