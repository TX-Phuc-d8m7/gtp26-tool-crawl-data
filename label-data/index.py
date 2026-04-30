import os
import json
import time
import re
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Nạp biến môi trường từ file .env
load_dotenv()

# --- CẤU HÌNH ---
API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=API_KEY)
MODEL_ID = 'gemini-2.5-flash-lite' 

VALID_SOFT = [
    "Đậm đà", "Thanh đạm", "Chua", "Cay", "Mặn", "Ngọt", "Đắng", "Béo ngậy",
    "Nóng hổi", "Thanh mát / Lạnh", "Món nước", "Món khô / Trộn",
    "Giòn / Giòn rụm", "Dai / Sần sật", "Mềm / Tan trong miệng", "Nước sền sệt",
    "Chiên / Rán", "Nướng", "Hấp / Luộc", "Xào", "Gỏi / Trộn sống",
    "Ăn no", "Ăn vặt", "Mồi nhậu", "Ăn sáng", "Ăn trưa", "Ăn xế", "Ăn đêm", "Tráng miệng", "Giải rượu", "Giải cảm / Ấm bụng",
    "Đặc sản Đà Nẵng", "Ẩm thực đường phố", "Món Việt truyền thống", "Món Á", "Món Âu"
]

# --- HÀM TRỢ GIÚP ---
def delay(seconds):
    time.sleep(seconds)

def clean_json_response(text):
    """Lọc bỏ các ký tự thừa để lấy đúng mảng JSON"""
    match = re.search(r'\[[\s\S]*\]', text)
    if match:
        return json.loads(match.group(0))
    raise ValueError("AI không trả về đúng định dạng JSON mảng")

async def tag_foods():
    try:
        output_file = "./raw_foods_enriched.json"
        enriched_data = []
        processed_names = set()

        if os.path.exists(output_file):
            with open(output_file, "r", encoding="utf-8") as f:
                try: 
                    enriched_data = json.load(f)
                    processed_names = {item.get("name") for item in enriched_data if item.get("name")}
                except json.JSONDecodeError:
                    print(f"⚠️ File output cũ bị lỗi định dạng, sẽ tạo mới.")

        # Đọc dữ liệu gốc
        with open("./raw_foods_input.json", "r", encoding="utf-8") as f:
            all_raw_data = json.load(f)

        raw_data = [item for item in all_raw_data if item.get("name") not in processed_names]

        total_new_items = len(raw_data)
        if total_new_items == 0:
            print("✅ Tất cả các món trong file gốc đều đã được xử lý từ trước!")
            return
        
        print(f"🚀 Bỏ qua {len(all_raw_data) - total_new_items} món đã có.")
        print(f"🚀 Tìm thấy {total_new_items} món mới cần xử lý...")

        batch_size = 10
        
        for i in range(0, total_new_items, batch_size):
            batch = raw_data[i : i + batch_size]

            print("-" * 50)
            print(f"⏳ [{time.strftime('%H:%M:%S')}] Đang xử lý Batch: Món {i + 1} -> {min(i + batch_size, total_new_items)} / Tổng {total_new_items}")
            for idx, item in enumerate(batch):
              print(f"   👉 Món {i + idx + 1}: {item.get('name', 'Không rõ tên')}")

            # --- NỘI DUNG PROMPT GIỮ NGUYÊN 100% ---
            prompt = f"""
        Nhiệm vụ: Hãy đóng vai chuyên gia ẩm thực, dinh dưỡng và Food Blogger. Dựa trên Tên và Nguyên liệu, hãy dán nhãn và viết mô tả cho danh sách món ăn sau.

        [DANH MỤC TAG HỢP LỆ]
        - Soft Filters: {", ".join(VALID_SOFT)}

        [QUY TẮC DÁN NHÃN QUAN TRỌNG]
        1. PHÂN TÍCH NGUYÊN LIỆU ẨN: Đọc kỹ "instructions" (cách làm) để tìm nguyên liệu KHÔNG có trong list "ingredients" (VD: chanh để rửa cá, muối để xát gà).
        2. Tuyệt đối không tự bịa ra tag mới ngoài danh sách đã cho.
        3. DỮ LIỆU GỐC: Trường "name" giữ nguyên nội dung 100%, trường "ingredients" phải giữ nguyên 100% không thay đổi.
        4. PHÂN LOẠI USAGE:
            - "preprocessing_ingredients": Nếu chỉ dùng để sơ chế, rửa, khử mùi, ngâm, hoặc ướp rồi bỏ đi (VD: chanh để chà cá, gừng ngâm khử mùi thịt, giấm rửa màng nhầy, ...).
            - "core_ingredients": Nếu là thành phần chính ăn được hoặc gia vị nấu trực tiếp trong món.
        5. Tên nguyên liệu phải được đưa về dạng Root Noun (VD: "500g thịt bò xắt lát" -> "thịt bò").


        [QUY TẮC VIẾT MÔ TẢ & GẮN NHÃN]
        - "soft_tags": 3-5 Chọn 3-5 tính chất phù hợp nhất từ danh sách [Soft Tags]. Tuyệt đối KHÔNG tự chế tag mới.
        - "description": Hãy viết một đoạn văn từ 3-5 câu miêu tả trải nghiệm ăn uống dựa TRÊN CƠ SỞ danh sách nguyên liệu (ingredients) được cung cấp.
            QUY TẮC CỐT LÕI (GROUNDING):
            1. Tuyệt đối chỉ suy luận từ "ingredients" được cung cấp. Không tự ý thêm nguyên liệu ngoài danh sách vào mô tả hay dán nhãn.
            2. Chỉ được suy luận hương vị từ nguyên liệu gốc (Ví dụ: có "ớt" thì tả "cay", có "me" thì tả "chua", có "xương ống" thì tả "ngọt thanh").
            3. Nếu danh sách nguyên liệu quá đơn giản, hãy tập trung tả kỹ về kết cấu và cảm giác ăn thay vì bịa thêm thành phần.

            YÊU CẦU PHONG CÁCH:
            - Tự nhiên như bài review, gợi cảm xúc.
            - Tập trung vào Khứu giác, Vị giác và Cảm giác (ấm bụng, bùng nổ vị giác, đưa cơm...).
            - Sử dụng từ ngữ đời thường mà người dùng hay dùng khi mô tả mong muốn tìm kiếm.
        
        [YÊU CẦU ĐẦU RA]
        Trả về DUY NHẤT một mảng JSON (không kèm giải thích). Cấu trúc mỗi đối tượng như sau:
        {{
          "name": "...",
          "core_ingredients": ["nguyên liệu 1", "nguyên liệu 2"],
          "preprocessing_ingredients": ["nguyên liệu sơ chế 1"],
          "soft_tags": ["4-6 tag Hương vị/Cảm xúc phù hợp nhất"],
          "description": "..."
        }}

        [DANH SÁCH CẦN XỬ LÝ]:
        {json.dumps(batch, ensure_ascii=False)}
            """

            try:
                # Gọi API
                response = client.models.generate_content(
                    model=MODEL_ID,
                    contents=[prompt],
                    config=types.GenerateContentConfig(
                        temperature=0.2,
                        response_mime_type="application/json",
                    )

                )
                processed_batch = clean_json_response(response.text)

                # So khớp số lượng thực tế AI trả về
                processed_count = min(len(processed_batch), len(batch))
                
                if processed_count < len(batch):
                    print(f"   ⚠️ Cảnh báo: AI chỉ xử lý được {processed_count}/{len(batch)} món trong batch này. Sẽ lưu {processed_count} món thành công.")

                # Hợp nhất dữ liệu
                for idx in range(processed_count):
                    # Python merge dictionary: {**a, **b}
                    item = batch[idx]
                    res = processed_batch[idx]
                    enriched_data.append({
                        "name": res.get("name"),
                        "description": res.get("description"),
                        "core_ingredients": res.get("core_ingredients"),
                        "preprocessing_ingredients": res.get("preprocessing_ingredients"),
                        "soft_tags": res.get("soft_tags"),
                        "raw_ingredients": item.get("ingredients", []),
                        "raw_instructions": item.get("instructions", "")
                    })

                    processed_names.add(res.get("name"))

                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(enriched_data, f, ensure_ascii=False, indent=2)

                # Delay để tránh Rate Limit
                delay(5)

            except Exception as e:
                print(f"❌ Lỗi tại vị trí {i}: {str(e)}")
                if "429" in str(e):
                    print("🛑 Rate Limit! Nghỉ 60s...")
                    delay(60)
                else:
                    delay(10)

        print("✅ Hoàn thành xử lí!")

    except Exception as err:
        print(f"💥 Lỗi hệ thống: {str(err)}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(tag_foods())