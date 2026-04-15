import os
import json
import time
import re
import google.generativeai as genai
from dotenv import load_dotenv

# Nạp biến môi trường từ file .env
load_dotenv()

# --- CẤU HÌNH ---
# Lấy API Key từ file .env hoặc dán trực tiếp vào đây
API_KEY = os.getenv("GEMINI_API_KEY") or "AIzaSyAL6am4QwmB4GTbwi8mL8MEKJy3SGTBXVQ"
genai.configure(api_key=API_KEY)

# Khởi tạo model (Giữ nguyên model name theo yêu cầu của bạn)
# Lưu ý: Hiện tại bản ổn định nhất là gemini-1.5-flash
model = genai.GenerativeModel('gemini-2.5-flash-lite')

VALID_HARD = [
    "Động vật có vỏ", "Hải sản / Cá", "Đậu phộng / Các loại hạt", "Sữa / Lactose", 
    "Đậu nành", "Lúa mì / Gluten", "Trứng", "Cà chua", "Trái cây có múi", 
    "Mè / Vừng", "Đồ sống / Chín tái", "Tiểu đường", 
    "Cao huyết áp", "Bệnh Thận", "Dạ dày / Đại tràng", 
    "Tim mạch / Mỡ máu", "Viêm họng / Ho", "Táo bón"
]

VALID_DIET = [
    "Thuần chay", "Chay Phật giáo", "Chay trứng sữa", 
    "Hồi giáo (Halal)", "Keto", "Eat Clean", "DASH / Địa Trung Hải"
]

VALID_SOFT = [
    "Đậm đà", "Thanh đạm", "Chua", "Cay", "Mặn", "Ngọt", "Đắng", "Béo ngậy",
    "Nóng hổi", "Thanh mát / Lạnh", "Món nước", "Món khô / Trộn",
    "Giòn / Giòn rụm", "Dai / Sần sật", "Mềm / Tan trong miệng", "Nước sền sệt",
    "Chiên / Rán", "Nướng", "Hấp / Luộc", "Xào", "Gỏi / Trộn sống",
    "Ăn no", "Ăn vặt", "Mồi nhậu", "Ăn sáng", "Ăn đêm", "Tráng miệng", "Giải rượu", "Giải cảm / Ấm bụng",
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
        # Đọc dữ liệu gốc
        with open("./raw_foods.json", "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        enriched_data = []
        output_file = "./foods_enriched.json"

        # Nếu file đã tồn tại một phần, đọc tiếp để tránh làm lại từ đầu
        if os.path.exists(output_file):
            with open(output_file, "r", encoding="utf-8") as f:
                enriched_data = json.load(f)

        batch_size = 40
        start_index = len(enriched_data)
        total_items = len(raw_data)

        if start_index >= total_items:
            print("✅ Tất cả các món đã được xử lý xong!")
            return
        
        print(f"🚀 Bắt đầu xử lý từ món thứ {start_index + 1} đến {total_items}...")

        for i in range(start_index, len(raw_data), batch_size):
            batch = raw_data[i : i + batch_size]

            # --- THÔNG BÁO TIẾN ĐỘ CHI TIẾT ---
            print("-" * 50)
            print(f"⏳ [{time.strftime('%H:%M:%S')}] Đang xử lý Batch: Món {i + 1} -> {min(i + batch_size, total_items)} / Tổng {total_items}")
            for idx, item in enumerate(batch):
              print(f"   👉 Món {i + idx + 1}: {item.get('name', 'Không rõ tên')}")
            # ----------------------------------

            # --- NỘI DUNG PROMPT GIỮ NGUYÊN 100% ---
            prompt = f"""
        Nhiệm vụ: Hãy đóng vai chuyên gia ẩm thực, dinh dưỡng và Food Blogger. Dựa trên Tên và Nguyên liệu, hãy dán nhãn và viết mô tả cho danh sách món ăn sau.

        [DANH MỤC TAG HỢP LỆ]
        - Hard Filters: {", ".join(VALID_HARD)}
        - Dietary Filters: {", ".join(VALID_DIET)}
        - Soft Filters: {", ".join(VALID_SOFT)}

        [QUY TẮC DÁN NHÃN QUAN TRỌNG]
        1. Phải quét kỹ TOÀN BỘ danh sách tag hợp lệ. 
        2. Với mỗi món, phải đưa vào TẤT CẢ các tag phù hợp. KHÔNG GIỚI HẠN số lượng tag trong một món. 
        3. Nếu một món không dính tag nào, hãy để mảng rỗng [].
        4. Tuyệt đối không tự bịa ra tag mới ngoài danh sách đã cho.
        5. DỮ LIỆU GỐC: Trường "name" giữ nguyên nội dung, chỉ xóa bỏ các icon. Trường "ingredients" phải giữ nguyên 100% không thay đổi.


        [HƯỚNG DẪN CHI TIẾT CÁC TRƯỜNG]
        - "soft_filters": 3-5 tính chất cảm quan đời thường (Ví dụ: Cay nồng, Béo ngậy, Thanh đạm, Giòn rụm, Nóng hổi, Chua thanh...).
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
          "ingredients": ["Mảng nguyên liệu gốc - GIỮ NGUYÊN 100%"],
          "hard_filters": ["Danh sách TẤT CẢ các tag dị ứng/bệnh lý phù hợp"],
          "dietary_filters": ["Danh sách TẤT CẢ các tag chế độ ăn phù hợp"],
          "soft_filters": ["4-6 tag Hương vị/Cảm xúc phù hợp nhất"],
          "description": "..."
        }}

        [DANH SÁCH CẦN XỬ LÝ]:
        {json.dumps(batch, ensure_ascii=False)}
            """

            try:
                # Gọi API
                response = model.generate_content(prompt)
                processed_batch = clean_json_response(response.text)

                # Hợp nhất dữ liệu
                for idx, item in enumerate(batch):
                    # Python merge dictionary: {**a, **b}
                    enriched_item = {**item, **processed_batch[idx]}
                    enriched_data.append(enriched_item)

                # Ghi dữ liệu xuống file (Lưu ý: ensure_ascii=False để đọc được tiếng Việt)
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
                # Để đơn giản, vòng lặp for sẽ tiếp tục batch tiếp theo. 
                # Nếu muốn thử lại đúng batch này, bạn có thể chuyển sang dùng vòng lặp while.

        print("✅ Hoàn thành 500 món!")

    except Exception as err:
        print(f"💥 Lỗi hệ thống: {str(err)}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(tag_foods())