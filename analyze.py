import csv
import json
import statistics
from datetime import datetime
from collections import defaultdict

CSV_FILE = "bus_log.csv"
OUTPUT_FILE = "schedule.json"
VISIT_GAP_MINS = 15    # 同一車牌在同一站，超過 15 分鐘視為下一趟車
CLUSTER_GAP_MINS = 20  # 不同天的到站時間差距超過 20 分鐘，視為不同班次

def mins_to_str(m):
    h = int(m) // 60
    mm = int(m) % 60
    return f"{h:02d}:{mm:02d}"

def main():
    # 1. 讀取並依 (縣市, 路線, 方向, 站名, 車牌, 日期) 分組
    raw_groups = defaultdict(list)
    with open(CSV_FILE, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            gps_str = row.get("GPS時間", "").strip()
            if not gps_str:
                continue
            try:
                dt = datetime.fromisoformat(gps_str)
            except ValueError:
                continue

            key = (
                row["縣市"],
                row["路線"],
                row["方向"],
                row["站名"],
                row["車牌"],
                dt.strftime("%Y-%m-%d")
            )
            raw_groups[key].append((dt, row["狀態"]))

    # 2. 過濾出每一趟車在各站的「單一代表時間」（優先最早進站，其次最早離站）
    stop_times = defaultdict(list)

    for (city, route, direction, stop, plate, date_str), events in raw_groups.items():
        events.sort(key=lambda x: x[0])

        # 切分同車牌在同一天的不同趟次
        visits = []
        current_visit = [events[0]]
        for ev in events[1:]:
            if (ev[0] - current_visit[-1][0]).total_seconds() / 60 > VISIT_GAP_MINS:
                visits.append(current_visit)
                current_visit = [ev]
            else:
                current_visit.append(ev)
        visits.append(current_visit)

        day_type = "假日" if datetime.strptime(date_str, "%Y-%m-%d").weekday() >= 5 else "平日"

        for visit in visits:
            arrivals = [dt for dt, status in visit if status == "進站"]
            departures = [dt for dt, status in visit if status == "離站"]
            target_dt = min(arrivals) if arrivals else min(departures)
            
            mins_of_day = target_dt.hour * 60 + target_dt.minute
            stop_times[(city, route, direction, stop, day_type)].append(mins_of_day)

    # 3. 班次分群並計算統計區間
    result = {}
    for (city, route, direction, stop, day_type), times in stop_times.items():
        times.sort()
        clusters = []
        curr = [times[0]]
        for t in times[1:]:
            if t - curr[-1] > CLUSTER_GAP_MINS:
                clusters.append(curr)
                curr = [t]
            else:
                curr.append(t)
        clusters.append(curr)

        route_key = f"{city}_{route}"
        result.setdefault(route_key, {}).setdefault(direction, {}).setdefault(stop, {})[day_type] = [
            {
                "最早": mins_to_str(min(c)),
                "常見": mins_to_str(statistics.median(c)),
                "最晚": mins_to_str(max(c)),
                "樣本數": len(c)
            }
            for c in clusters
        ]

    with open(OUTPUT_FILE, mode="w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"分析完成，已更新 {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
