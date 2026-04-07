import cloudscraper
from bs4 import BeautifulSoup
import urllib.parse
import time
import json
import re

# Ham làm sạch nguyên liệu, loại bỏ số lượng, đơn vị đo lường và các thông tin không cần thiết
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
    # Lưu ý: Sắp xếp các từ dài lên trước để tránh xóa nhầm (ví dụ: 'muỗng cafe' trước 'muỗng')
    units = [
        'muỗng cafe', 'muỗng cà phê', 'muỗng canh', 'muỗng', 'tsp', 'tbsp', 
        'lít', 'lit', 'kg', 'kilogam', 'gam', 'gram', 'lạng', 'củ', 'cây', 
        'tô', 'bát', 'chén', 'quả', 'trái', 'con', 'khoảng', 'bó', 'miếng', 'cm', 
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

DANH_SACH_TEST = ["Phở bò tái lăn", "Phở bò nạm gầu", "Phở gà ta", "Bún bò Huế (Giò, gân, chả)",
"Bún bò bắp", "Bún riêu cua đồng", "Bún ốc", "Bún thịt nướng",
"Bún chả Hà Nội", "Bún đậu mắm tôm", "Miến lươn trộn", "Miến lươn nước",
"Miến măng gà", "Miến xào hải sản", "Mì vằn thắn", "Hủ tiếu Nam Vang",
"Hủ tiếu gõ", "Hủ tiếu mực", "Bún bề bề", "Bánh đa cua",
"Phở cuốn Hà Nội", "Phở xào mềm", "Bún cá rô đồng", "Bún chả cá Quy Nhơn",
"Bún sườn sụn nấu sấu", "Bún dọc mùng", "Hủ tiếu Nam Vang khô (trộn)", "Mì xào giòn hải sản",
"Bánh đa cua bể", "Bún thang", "Miến xào cua", "Bún cá ngừ", "Bún cá thu", "Bún cá lóc", "Bún cá rô đồng","Chíp chíp hấp sả", "Nghêu hấp thái", "Ốc hương rang muối tuyết", "Ốc hương xào bơ tỏi",
"Mực nhảy hấp hành gừng", "Mực nướng sa tế", "Mực một nắng nướng than", "Tôm sú nướng mắm nhĩ",
"Tôm hùm nướng phô mai", "Cua rang me", "Ghẹ xanh hấp", "Lẩu hải sản chua cay",
"Hàu nướng mỡ hành", "Hàu nướng phô mai", "Sò điệp nướng mỡ hành", "Nhum biển nướng trứng",
"Cá mú hấp xì dầu", "Cá đuối nướng mỡ hành", "Sò huyết rang me", "Tôm tít (bề bề) rang muối",
"Lẩu cá bớp măng chua", "Cua huỳnh đế hấp", "Mực sữa chiên nước mắm", "Bạch tuộc nướng sa tế",
"Ốc móng tay xào rau muống", "Ốc len xào dừa", "Sò lông nướng mỡ hành", "Cháo hàu",
"Gỏi sứa trộn vả", "Còi biên mai nướng muối ớt", "Tôm hùm đất (Crawfish) sốt Cajun","Mì Quảng Ếch", "Mì Quảng Tôm Thịt", "Mì Quảng Gà ta", "Mì Quảng Cá lóc",
"Mì Quảng Bò", "Mì Quảng Sứa", "Bún chả cá Đà Nẵng", "Bún cá ngừ",
"Bún sứa nước lèo", "Bún mắm nêm heo quay", "Bún mắm nêm nem chả",
"Bún mắm nêm thịt luộc", "Bánh tráng cuốn thịt heo hai đầu da"]
scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'darwin', 'desktop': True})

results = []

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
            recipe_name = detail_soup.find('h1').get_text(strip=True) if detail_soup.find('h1') else mon_an
            
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
            
            # Lưu vào danh sách kết quả
            data = {
                "name": recipe_name,
                "ingredients": ingredients
            }
            results.append(data)
            print(f"   ✅ Đã lấy xong {len(ingredients)} nguyên liệu.")
        else:
            print(f"   ❌ Không tìm thấy link cho: {mon_an}")

    except Exception as e:
        print(f"   ❌ Lỗi: {e}")
        
    time.sleep(2) # Nghỉ một chút để tránh bị block

# --- XUẤT KẾT QUẢ RA JSON ---
with open("recipes07-bun-pho-mien.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=4)

print("\n✨ Hoàn thành! Dữ liệu đã được lưu vào file")