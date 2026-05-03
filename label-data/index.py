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
PROJECT_ID = os.getenv("PROJECT_ID")
client = genai.Client(vertexai=True, project=PROJECT_ID)
MODEL_ID = 'gemini-2.5-flash' 

VALID_SOFT = [
    # Nhóm 1: Hương vị
    "Đậm đà", "Thanh đạm", "Chua", "Cay", "Mặn", "Ngọt", "Đắng", "Béo ngậy",

    # Nhóm 2: Nhiệt độ & Cảm giác
    "Nóng hổi", "Thanh mát/Giải nhiệt", "Món nước", "Món khô", "Nước sền sệt", "Món lạnh", "Sống/Chín tái"

    # Nhóm 3: Kết cấu
    "Giòn / Giòn rụm", "Dai / Sần sật", "Mềm", 

    # Nhóm 4: Phương pháp chế biến
    "Chiên / Rán", "Nướng", "Hấp / Luộc", "Xào", "Gỏi / Nộm / Trộn", "Cuốn / Gói", "Hầm / Ninh", "Lẩu", "Kho/Rim", "Súp", "Cháo"

    # Nhóm 5: Thời điểm trong ngày và dịp ăn uống
    "Ăn no", "Ăn vặt", "Mồi nhậu", "Ăn sáng", "Ăn trưa", "Ăn chiều/xế", "Ăn tối", "Ăn khuya", "Tráng miệng", "Giải rượu", "Giải cảm", "Ấm bụng"

    # Nhóm 6: Phong cách ẩm thực
    "Đặc sản Đà Nẵng", "Ẩm thực đường phố", "Món Việt truyền thống", "Món Á", "Món Âu", "Thức ăn nhanh", "Món chay",

    # Nhóm 7: Đặc điểm dinh dưỡng
    "Giàu chất xơ", "Giàu đạm", "Giàu vitamin", "Nội tạng", "Sữa / Phô mai", "Thực phẩm chế biến sẵn", "Bánh ngọt"
]

# Danh sách từ khóa nội tạng dùng cho Python Fallback
OFFAL_KEYWORDS = ["gan", "lòng", "mề", "óc", "tim", "cật", "dồi", "ruột", "bao tử", "dạ dày", "phèo", "huyết", "tiết", "pín"]

# Danh sách các món đặc sản Đà Nẵng
DANANG_KEYWORDS = [
    "mì quảng", "mỳ quảng", "bún chả cá", 
    "bún mắm nêm", "bún thịt nướng", "bánh tráng cuốn thịt heo", 
    "bánh xèo", "nem lụi", "bánh bèo", "mít non trộn", "ốc hút", 
    "gỏi cá", "tré", "bánh đập", "bún mắm", "cao lầu"
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

def contains_offal(ingredients):
    """Kiểm tra xem mảng nguyên liệu có chứa từ khóa nội tạng không"""
    if not ingredients:
        return False
    text = " ".join(ingredients).lower()
    for keyword in OFFAL_KEYWORDS:
        # Dùng regex để tìm từ độc lập, tránh match sai (VD: "gan" không match "gạo tẻ ngon")
        if re.search(rf'\b{keyword}\b', text):
            return True
    return False

def is_danang_specialty(food_name):
    """Kiểm tra xem tên món ăn có chứa từ khóa đặc sản Đà Nẵng không"""
    if not food_name:
        return False
    name_lower = food_name.lower()
    for keyword in DANANG_KEYWORDS:
        if keyword in name_lower:
            return True
    return False

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

        batch_size = 50
        
        for i in range(0, total_new_items, batch_size):
            batch = raw_data[i : i + batch_size]

            print("-" * 50)
            print(f"⏳ [{time.strftime('%H:%M:%S')}] Đang xử lý Batch: Món {i + 1} -> {min(i + batch_size, total_new_items)} / Tổng {total_new_items}")
            for idx, item in enumerate(batch):
              print(f"   👉 Món {i + idx + 1}: {item.get('name', 'Không rõ tên')}")

            # --- NỘI DUNG PROMPT GIỮ NGUYÊN 100% ---
            prompt = f"""
        Nhiệm vụ: Hãy đóng vai chuyên gia ẩm thực, dinh dưỡng và Food Blogger. Dựa trên Tên và Nguyên liệu (ingredients) và cách làm (instructions) hãy dán nhãn, viết mô tả và chuẩn hoá dữ liệu cho danh sách món ăn sau.

        [DANH MỤC TAG HỢP LỆ]
        - Soft Filters: {", ".join(VALID_SOFT)}

        [QUY TẮC PHÂN LOẠI NGUYÊN LIỆU (ingredients) - BẮT BUỘC LÀM THEO 3 BƯỚC]
        Bạn phải chạy logic thuật toán sau trong đầu để chia nguyên liệu:
        
        - BƯỚC 1 (Chuẩn hoá Data gốc): Lấy mảng "ingredients" ban đầu ra. Lập tức RÚT GỌN toàn bộ tên nguyên liệu về dạng Root Noun (VD: "bì sữa tươi không đường" -> "sữa tươi không đường", "500g thịt bò xắt lát" -> "thịt bò"). Ta gọi đây là [Mảng Nguyên Liệu Chuẩn].
        
        - BƯỚC 2 (Xác định Preprocessing - Chất khử mùi/Ngâm xả): Đọc kỹ "instructions". Tìm các hành động "rửa", "ngâm", "chà xát", "chần", "khử mùi". Rút trích các nguyên liệu đi kèm MÀ SAU ĐÓ BỊ RỬA TRÔI/ĐỔ BỎ (Ví dụ: sữa tươi ngâm gan rồi rửa, chanh để chà cá, muối xát gà, rượu chần thịt). Đưa chúng vào "preprocessing_ingredients". 
          🚨 LƯU Ý: Tuyệt đối KHÔNG đưa nguyên liệu thịt/cá/rau (như gan, ếch, bò...) vào mảng này.

        - BƯỚC 3 (Xác định Core - Nguyên liệu cấu thành): Lấy toàn bộ mảng "ingredients" gốc, CỘNG THÊM các gia vị/nguyên liệu được nhắc đến trong "instructions" (nếu có). Sau đó ĐỐI CHIẾU VÀ LOẠI BỎ hoàn toàn những nguyên liệu đã bị phân vào "preprocessing_ingredients" ở Bước 1. 
          + Nếu một chất (VD: muối, rượu) CHỈ xuất hiện ở hành động sơ chế (Bước 2) -> Xoá nó khỏi Core.
          + TRƯỜNG HỢP ĐA NHIỆM: Nếu một chất (VD: muối) VỪA được dùng để ngâm rửa, VỪA được dùng để tẩm ướp/nấu nước sốt -> Giữ nguyên nó ở Core, VÀ cho phép nó xuất hiện ở cả Preprocessing.        
        - BƯỚC 4 (Kỷ luật chống ảo giác): Tự kiểm tra lại 2 mảng vừa tạo. TUYỆT ĐỐI CHỈ DÙNG những nguyên liệu thực sự xuất hiện trong văn bản gốc ("ingredients" và "instructions"). KHÔNG ĐƯỢC TỰ SUY DIỄN, không được bịa ra nguyên liệu không có trong bài (Ví dụ: Bài không ghi dầu ăn thì không được tự thêm dầu ăn vào).

        [QUY TẮC CHUẨN HOÁ VÀ DÁN NHÃN QUAN TRỌNG]
        1. Dữ liệu gốc: Trường "name" giữ nguyên nội dung 100%, trường "ingredients" phải giữ nguyên 100% không thay đổi.
        2. Chuẩn hoá tên: Tên nguyên liệu phải được đưa về dạng Root Noun (VD: "500g thịt bò xắt lát" -> "thịt bò", "1/2 muỗng muối" -> "muối").
        3. Dán nhãn Soft Tags: Chọn 3-5 tag phù hợp nhất từ danh sách [Soft Filters] dựa trên trải nghiệm ăn uống mà bạn hình dung được từ nguyên liệu và cách làm. Tuyệt đối KHÔNG tự chế tag mới ngoài danh sách đã cho.

        [QUY TẮC VIẾT MÔ TẢ & GẮN NHÃN]
        - "soft_tags": Chọn 3-5 tính chất phù hợp nhất từ danh sách [Soft Filters]. Tuyệt đối KHÔNG tự chế tag mới.
        - "description": Hãy viết một đoạn văn từ 3-5 câu miêu tả trải nghiệm ăn uống dựa TRÊN CƠ SỞ danh sách nguyên liệu (ingredients) được cung cấp.
            QUY TẮC CỐT LÕI (GROUNDING):
            1. Tuyệt đối chỉ suy luận từ "ingredients" được cung cấp. Không tự ý thêm nguyên liệu ngoài danh sách vào mô tả hay dán nhãn.
            2. Chỉ được suy luận hương vị từ nguyên liệu gốc (Ví dụ: có "ớt" thì tả "cay", có "me" thì tả "chua", có "xương ống" thì tả "ngọt thanh").
            3. Nếu danh sách nguyên liệu quá đơn giản, hãy tập trung tả kỹ về kết cấu và cảm giác ăn thay vì bịa thêm thành phần.
            4. BẮT BUỘC VỚI NHÃN "Nội tạng": NẾU trong nguyên liệu (ingredients) CÓ CHỨA các thành phần như gan, lòng, mề, óc, tim, cật, dồi, ruột, bao tử, dạ dày, huyết/tiết (của heo, bò, gà...) thì BẠN BẮT BUỘC PHẢI THÊM TAG "Nội tạng" vào mảng "soft_tags".

            [QUY TẮC DÁN NHÃN THỜI ĐIỂM (MEALTIME TAGS) - DỰA TRÊN VĂN HÓA VIỆT NAM]
            Khi chọn tag thuộc Nhóm Thời Điểm ("Ăn sáng", "Ăn trưa", "Ăn tối", "Ăn khuya", "Ăn vặt", "Ăn xế"), BẮT BUỘC áp dụng các nguyên tắc sau:
            1. "Ăn sáng": Ưu tiên các món ăn nhanh gọn, có nước hoặc tinh bột dễ tiêu (VD: Bún, phở, miến, hủ tiếu, xôi, bánh mì, bánh cuốn, cháo).
            2. "Ăn trưa" & "Ăn tối": Đây là bữa chính ("Ăn no"). Dành cho các món ăn kèm với cơm trắng (thịt kho, cá kho, canh, rau xào), hoặc các món ăn no lâu, cầu kỳ (Lẩu, Nướng, Cơm tấm, Bún đậu mắm tôm). Thường các món ăn trưa cũng có thể ăn tối.
            3. "Ăn vặt" / "Ăn xế": Các món ăn chơi, không làm no ngang, thường có vị chua/ngọt hoặc đồ nhắm (VD: Chè, bánh tráng trộn, gỏi cuốn, ốc, nem chua rán, trái cây tô).
            4. "Ăn đêm / Ăn khuya": Các món ấm bụng, dễ tiêu hoặc đồ nhậu nhẹ (VD: Cháo, mì gõ, súp, hột vịt lộn, khô mực). Tuyệt đối không gắn "Ăn khuya" cho các món quá nặng bụng như Cơm nếp, Bánh chưng.
            Lưu ý: Một món có thể có nhiều thời điểm (VD: Phở có thể "Ăn sáng" và "Ăn đêm"). Hãy linh hoạt chọn 1-3 tag thời điểm hợp lý nhất.

            [QUY TẮC PHÂN BIỆT MÓN NƯỚC, CHÁO VÀ SÚP]
            Để hệ thống gợi ý chính xác thì BẮT BUỘC tuân thủ:
            1. NẾU món ăn là Cháo (tên có chữ "cháo", nấu từ gạo ninh nhừ): BẮT BUỘC gán tag "Cháo". Ưu tiên kèm tag "Nước sền sệt". Hạn chế dùng tag "Món nước" chung chung.
            2. NẾU món ăn là Súp (tên có chữ "súp/soup", nấu sệt bằng bột năng/bột bắp): BẮT BUỘC gán tag "Súp". Ưu tiên kèm tag "Nước sền sệt". Hạn chế dùng tag "Món nước".
            3. Nhãn "Món nước" CHỈ DÀNH CHO các món có nước lèo lỏng, trong (VD: Bún, Phở, Mì, Miến, Canh, Lẩu).

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

                    food_name = res.get("name", "")
                    food_name_lower = food_name.lower()
                    raw_ingredients_list = item.get("ingredients", [])
                    soft_tags_list = res.get("soft_tags", [])

                    soft_tags_list = [tag for tag in soft_tags_list if tag in VALID_SOFT]

                    # 1. Vá lỗi NỘI TẠNG (Quét qua mảng ingredients gốc)
                    has_offal_keyword = contains_offal(raw_ingredients_list)
                    if has_offal_keyword:
                        if "Nội tạng" not in soft_tags_list:
                            soft_tags_list.append("Nội tạng")
                            print(f"   🔧 [Auto-Fix] Thêm tag 'Nội tạng' cho món: {food_name}")
                        else:
                        # Nếu thành phần nguyên liệu không có nội tạng mà AI tự gắn thì xóa đi
                            if "Nội tạng" in soft_tags_list:
                                soft_tags_list.remove("Nội tạng")
                                print(f"   🧹 [Auto-Clean] Xóa tag 'Nội tạng' ảo giác cho món: {food_name}")

                    if is_danang_specialty(food_name):
                        if "Đặc sản Đà Nẵng" not in soft_tags_list:
                            soft_tags_list.append("Đặc sản Đà Nẵng")
                            print(f"   🌟 [Auto-Fix] Thêm tag 'Đặc sản Đà Nẵng' cho món: {food_name}")

                    # 2. Vá lỗi cho món CHÁO
                    if "cháo" in food_name_lower:
                        if "Cháo" not in soft_tags_list:
                            soft_tags_list.append("Cháo")
                            print(f"   🔧 [Auto-Fix] Thêm tag 'Cháo' cho món: {food_name}")
                        if "Món nước" in soft_tags_list:
                            soft_tags_list.remove("Món nước") # Xóa tag chung chung
                            
                    # 3. Vá lỗi cho món SÚP
                    if "súp" in food_name_lower or "soup" in food_name_lower:
                        if "Súp" not in soft_tags_list:
                            soft_tags_list.append("Súp")
                            print(f"   🔧 [Auto-Fix] Thêm tag 'Súp' cho món: {food_name}")
                        if "Món nước" in soft_tags_list:
                            soft_tags_list.remove("Món nước")

                    # 5. Vá lỗi cho BÁNH MÌ
                    if "bánh mì" in food_name_lower or "bánh mỳ" in food_name_lower:
                        added_tags = []
                        if "Món khô" not in soft_tags_list: added_tags.append("Món khô")
                        if "Giòn / Giòn rụm" not in soft_tags_list: added_tags.append("Giòn / Giòn rụm")
                        if added_tags:
                            soft_tags_list.extend(added_tags)
                            print(f"   🥖 [Auto-Fix] Thêm tag {added_tags} cho món: {food_name}")
                        # Xóa nhầm lẫn nếu AI lỡ gán
                        if "Món nước" in soft_tags_list: soft_tags_list.remove("Món nước")

                    # 6. Vá lỗi cho XÔI
                    if re.search(r'\bxôi\b', food_name_lower): # Dùng \b để tránh bắt nhầm chữ "khúc xôi" (nếu có)
                        added_tags = []
                        if "Món khô" not in soft_tags_list: added_tags.append("Món khô")
                        if "Mềm" not in soft_tags_list: added_tags.append("Mềm")
                        if added_tags:
                            soft_tags_list.extend(added_tags)
                            print(f"   🍚 [Auto-Fix] Thêm tag {added_tags} cho món: {food_name}")
                        if "Món nước" in soft_tags_list: soft_tags_list.remove("Món nước")

                    # 7. Vá lỗi BỮA ĂN CHÍNH (Cơm, Canh, Xào, Kho)
                    # Dùng Regex \b để bắt từ độc lập. 
                    # Ví dụ: bắt "canh" trong "Canh chua", nhưng BỎ QUA "canh" trong "Bánh canh"
                    if re.search(r'\b(cơm|canh|xào|kho)\b', food_name_lower):
                        if "Ăn trưa" not in soft_tags_list and "Ăn tối" not in soft_tags_list:
                            soft_tags_list.extend(["Ăn trưa", "Ăn tối"])
                            print(f"   🍛 [Auto-Fix] Thêm tag ['Ăn trưa', 'Ăn tối'] cho món: {food_name}")

                    # 8. Vá lỗi cho TỪ SỮA / PHÔ MAI
                    if re.search(r'\b(phô mai|sữa chua|kem|yaourt|bơ|flan|panna cotta|mousse)\b', food_name_lower) or \
                       re.search(r'\b(sữa tươi|sữa đặc|phô mai|whipping cream|bơ lạt)\b', " ".join(raw_ingredients_list).lower()):
                        added_tags = []
                        if "Từ sữa / Phô mai" not in soft_tags_list: added_tags.append("Từ sữa / Phô mai")
                        if "Béo ngậy" not in soft_tags_list: added_tags.append("Béo ngậy") # Đồ sữa thường béo
                        if added_tags:
                            soft_tags_list.extend(added_tags)
                            print(f"   🧀 [Auto-Fix] Thêm tag {added_tags} cho món: {food_name}")

                    # 9. Vá lỗi cho THỰC PHẨM CHẾ BIẾN SẴN
                    if re.search(r'\b(cá viên|bò viên|tôm viên|xúc xích|lạp xưởng|hồ lô|nem chua rán|dồi sụn)\b', food_name_lower) or \
                       re.search(r'\b(cá viên|bò viên|xúc xích|lạp xưởng)\b', " ".join(raw_ingredients_list).lower()):
                        if "Thực phẩm chế biến sẵn" not in soft_tags_list:
                            soft_tags_list.append("Thực phẩm chế biến sẵn")
                            print(f"   🍢 [Auto-Fix] Thêm tag 'Thực phẩm chế biến sẵn' cho món: {food_name}")
                            
                    # 10. Vá lỗi Kẹp chung cho Tráng miệng / Ăn vặt
                    # Nếu có chữ "kem", "sữa chua", "rau câu" -> auto Tráng miệng
                    if re.search(r'\b(kem|sữa chua|yaourt|rau câu|bingsu|flan)\b', food_name_lower):
                        if "Tráng miệng" not in soft_tags_list:
                            soft_tags_list.append("Tráng miệng")
                            print(f"   🍨 [Auto-Fix] Thêm tag 'Tráng miệng' cho món: {food_name}")
                        if "Món lạnh" not in soft_tags_list: # Sữa chua, kem thì auto lạnh
                            soft_tags_list.append("Món lạnh")

                    enriched_data.append({
                        "name": res.get("name"),
                        "description": res.get("description"),
                        "core_ingredients": res.get("core_ingredients"),
                        "preprocessing_ingredients": res.get("preprocessing_ingredients"),
                        "soft_tags": soft_tags_list,
                        "raw_ingredients": raw_ingredients_list,
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