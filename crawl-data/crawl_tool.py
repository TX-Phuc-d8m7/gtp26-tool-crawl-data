import cloudscraper
from bs4 import BeautifulSoup
import urllib.parse
import time
import json
import re
import os

# ---------- DANH SÁCH HÀM ----------

# 1. Hàm làm sạch nguyên liệu, loại bỏ số lượng, đơn vị đo lường và các thông tin không cần thiết
def clean_ingredient(text):
    # 1. Chuyển về chữ thường
    text = text.lower()
    
    # 2. Xóa nội dung trong ngoặc (...) và [...] bao gồm cả dấu ngoặc
    text = re.sub(r'[\(\[].*?[\)\]]', '', text)
    
    # 3. Thay thế các ký tự ngắt (dấu +, "và", dấu phẩy, dấu chấm) bằng dấu phẩy để dễ split
    # Sử dụng regex để tìm " và " (có khoảng trắng) hoặc các dấu câu
    text = re.sub(r'(\s+và\s+|[\+\,\.])', ',', text)
    
    # 4. Xóa số và các ký tự phân số (1, 2, 1/2, 0.5,...)
    text = re.sub(r'\d+([\/\.]\d+)?', '', text)
    
    # 5. Danh sách các đơn vị đo lường cần xóa
    units = [
        'muỗng cafe', 'muỗng cà phê', 'muỗng cf', 'muỗng canh', 'muỗng', 'tsp', 'tbsp', 
        'lít', 'lit', 'kg', 'kilogam', 'gam', 'gram', 'lạng', 'củ', 'cây', 
        'tô', 'bát', 'chén', 'quả', 'trái', 'con', 'khoảng', 'bó', 'miếng', 'cm', 'gr'
    ]
    # Tạo regex pattern cho units: \b(unit1|unit2)\b để khớp chính xác từ
    unit_pattern = r'\b(' + '|'.join(units) + r')\b'
    text = re.sub(unit_pattern, '', text)
    
    # 6. Tách theo dấu phẩy đã tạo ở bước 3
    parts = text.split(',')
    
    final_list = []
    for p in parts:
        # Làm sạch khoảng trắng thừa
        clean_p = " ".join(p.split())
        # Chỉ thêm vào list nếu còn nội dung và không chỉ là ký tự đặc biệt
        if clean_p and len(clean_p) > 1:
            final_list.append(clean_p)
            
    return final_list



# --- DANH SÁCH MÓN ĂN CẦN CRAWL ---
current_dir = os.path.dirname(os.path.abspath(__file__))
FOOD_LIST_TEST = os.path.join(current_dir, "..", "clean-data", "food_name_instruction.json")
try:
    with open(FOOD_LIST_TEST, "r", encoding="utf-8") as f:
        DANH_SACH_TEST = json.load(f)
    print(f"🚀 Bắt đầu crawl với {len(DANH_SACH_TEST)} món ăn từ file {FOOD_LIST_TEST}")
except Exception as e:
    print(f"❌ Lỗi khi đọc file JSON: {e}")
    DANH_SACH_TEST = []



# --- CẤU HÌNH SCRAPER ---
scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'darwin', 'desktop': True})




# --- KẾT QUẢ THU ĐƯỢC ---
results = []
not_found_links = []
print("--- ĐANG CRAWL DỮ LIỆU CHI TIẾT ---")
for mon_an in DANH_SACH_TEST:
    print(f"\n🔍 Đang xử lý: {mon_an}")
    query = urllib.parse.quote(mon_an)
    search_url = f"https://cookpad.com/vn/tim-kiem/{query}"
    try:
        # 1. Lấy link chi tiết
        response = scraper.get(search_url)
        soup = BeautifulSoup(response.text, 'html.parser')
        all_links = soup.find_all('a', href=lambda href: href and '/vn/cong-thuc/' in href)
        
        recipe_url = None
        for link in all_links:
            href = link['href']
            if "tao-moi" not in href and "search" not in href:
                recipe_url = href if href.startswith("http") else "https://cookpad.com" + href
                break 

        if recipe_url:
            # 2. Truy cập vào link chi tiết để lấy nguyên liệu
            print(f"   -> Đang truy cập: {recipe_url}")
            detail_res = scraper.get(recipe_url)
            detail_soup = BeautifulSoup(detail_res.text, 'html.parser')
            
            # 3. Trích xuất tên món ăn (để đảm bảo chính xác theo bài viết)
            recipe_name = mon_an
            
            # 4. Trích xuất nguyên liệu
            # Cookpad thường để nguyên liệu trong các thẻ div có class "ingredient" hoặc div có itemprop
            ingredients = []
            
            # Tìm tất cả các vùng chứa nguyên liệu
            ingredient_tags = detail_soup.find_all(['div', 'li'], attrs={'itemprop': 'recipeIngredient'})
            
            # Nếu không tìm thấy bằng itemprop, thử tìm theo class phổ biến
            if not ingredient_tags:
                ingredient_tags = detail_soup.select('.ingredient-list li, .ingredient div')

            for item in ingredient_tags:

                # 1. Tìm tất cả các thẻ <bdi> nằm bên trong item và xóa chúng đi
                for bdi in item.find_all('bdi'):
                    bdi.decompose() 
                # --------------------------

                # 2. Lấy text, dùng separator là khoảng trắng để tránh dính chữ (như lỗi "bột gạotài kí")
                # Sau đó chuyển tất cả về chữ thường .lower()
                raw_text = item.get_text(" ", strip=True)
                # --------------------------

                # 3. Làm sạch nguyên liệu
                cleaned_ingredients = clean_ingredient(raw_text)
                ingredients.extend(cleaned_ingredients)

            # 4. Trích xuất phần hướng dẫn nấu ăn 
            instruction_steps = []
            
            # Cải thiện bộ lọc: Ưu tiên tìm theo thuộc tính itemprop của schema món ăn
            step_tags = detail_soup.find_all(['li', 'div'], attrs={'itemprop': 'recipeInstructions'})
            
            # Nếu không tìm thấy, dùng bộ lọc class cũ của bạn
            if not step_tags:
                step_tags = detail_soup.select('ol.list-none li p.overflow-wrap-anywhere')
            
            for idx, tag in enumerate(step_tags):
                # Lấy text (kiểm tra xem nó là thẻ p hay thẻ li)
                text = tag.get_text(strip=True)
                if text:
                    instruction_steps.append(f"{text}")

            # Trích xuất thêm phần "Bí quyết" (Advice) nếu có
            advice_section = detail_soup.find('div', id='advice')
            if advice_section:
                advice_text = advice_section.find('p', class_='overflow-wrap-anywhere')
                if advice_text:
                    # Thêm bí quyết như một bước cuối cùng hoặc ghi chú
                    instruction_steps.append(f"Bí quyết: {advice_text.get_text(strip=True)}")

            # Chuyển mảng thành chuỗi văn bản có xuống dòng
            full_instructions = "\n".join(instruction_steps)
            
            # Lưu vào danh sách kết quả
            data = {
                "name": recipe_name,
                "ingredients": ingredients,
                "instructions": full_instructions
            }
            results.append(data)
            print(f"   ✅ Đã lấy xong {len(ingredients)} nguyên liệu và {len(instruction_steps)} bước hướng dẫn.")
        else:
            print(f"   ❌ Không tìm thấy link cho: {mon_an}")
            not_found_links.append(mon_an)
    except Exception as e:
        print(f"   ❌ Lỗi: {e}")
        
    time.sleep(2) 



# --- XUẤT KẾT QUẢ RA JSON ---
out_dir = "label-data"
os.makedirs(out_dir, exist_ok=True)

with open(os.path.join(out_dir, "clean_food_ingredients1.json"), "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=4)



# --- DANH SÁCH MÓN KHÔNG TÌM THẤY ---
    if not_found_links:
        with open(os.path.join(out_dir, "not_found_foods1.json"), "w", encoding="utf-8") as f:
            json.dump(not_found_links, f, ensure_ascii=False, indent=4)
        print(f"\n⚠️ Đã lưu {len(not_found_links)} món không tìm thấy vào file 'not_found_foods.json'")
print("\n✨ Hoàn thành! Dữ liệu đã được lưu vào file")