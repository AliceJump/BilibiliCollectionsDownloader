import re

input_file = "./logs/biliCollectionDownloader_2026-06-10.log"
output_file = "./logs/act_ids_exists_true.txt"

act_ids = set()

with open(input_file, "r", encoding="utf-8") as f:
    for line in f:

        # ✔ 只匹配 exists=True 的“检查行”
        if "检查 act_id=" in line and "exists=True" in line:

            match = re.search(r"act_id=(\d+)", line)
            if match:
                act_ids.add(match.group(1))

with open(output_file, "w", encoding="utf-8") as f:
    for act_id in sorted(act_ids):
        f.write(act_id + "\n")

print(f"完成：{len(act_ids)} 个 exists=True act_id")