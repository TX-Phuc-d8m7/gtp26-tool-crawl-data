import os
import json
import time
import re
from google import genai
from google.genai import types
from dotenv import load_dotenv

# 1. Cấu hình môi trường
load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# 2. Danh sách bệnh lý mẫu (Bạn có thể nạp từ DB vào đây)
valid_health_tags = [
    "Có vết thương hở / Mới phẫu thuật",
    "Đang cho con bú",
    "Phụ nữ mang thai",
    "Gan nhiễm mỡ / Men gan cao",
    "Béo phì",
    "Đầy bụng / Khó tiêu",
    "Nhiệt miệng / Loét miệng",
    "Tiêu chảy",
    "Bệnh Gout",
    "Bệnh lý hô hấp trên (Ho/Viêm họng/Cảm/Amidan)",
    "Táo bón",
    "Bệnh tim mạch / Mỡ máu",
    "Trào ngược dạ dày",
    "Viêm loét dạ dày",
    "Bệnh suy thận",
    "Bệnh cao huyết áp",
    "Bệnh tiểu đường",
    "Dị ứng mắm lên men",
    "Dị ứng bột ngọt (MSG)",
    "Dị ứng mè / vừng",
    "Dị ứng trái cây có múi",
    "Dị ứng trứng",
    "Dị ứng cà chua",
    "Dị ứng lúa mì",
    "Dị ứng đậu nành",
    "Bất dung nạp Lactose",
    "Dị ứng sữa bò",
    "Dị ứng hạt cây",
    "Dị ứng đậu phộng",
    "Dị ứng cá có vây",
    "Dị ứng động vật thân mềm",
    "Dị ứng động vật giáp xác"
]

def supervisor_agent(user_input: str):
    system_instruction = f"""
    Bạn là chuyên gia phân tích ý định người dùng trong ẩm thực.
    Nhiệm vụ: Trích xuất thông tin sức khỏe và sở thích ăn uống.

    [DANH SÁCH TAG SỨC KHỎE HỢP LỆ]
    {valid_health_tags}

    [QUY TẮC PHÂN LOẠI]
    1. health_constraints: Chỉ chọn từ danh sách trên nếu người dùng bị bệnh hoặc dị ứng nghiêm trọng.
    2. exclude_ingredients: Danh sách các nguyên liệu người dùng KHÔNG MUỐN (không thích, kiêng, không ăn được, dị ứng).
       - Ví dụ: "Không thích hành" -> ["hành"]
       - Ví dụ: "Dị ứng tôm" -> ["tôm"]
    3. include_ingredients: Danh sách các nguyên liệu người dùng CẢM THẤY THÍCH hoặc YÊU CẦU.
       - Ví dụ: "Tôi thích ăn tôm" -> ["tôm"]
    
    [PHÂN BIỆT PHỦ ĐỊNH]
    - "Thích ăn X" -> đưa X vào include_ingredients.
    - "Không thích X", "Kiêng X", "Không ăn được X", "Dị ứng X" -> đưa X vào exclude_ingredients.
    """

    # Định nghĩa Schema chặt chẽ
    response_schema = {
        "type": "OBJECT",
        "properties": {
            "health_constraints": {
                "type": "ARRAY",
                "items": {"type": "STRING", "enum": valid_health_tags}
            },
            "exclude_ingredients": {
                "type": "ARRAY",
                "items": {"type": "STRING"},
                "description": "Các nguyên liệu cần loại bỏ (do ghét, kiêng hoặc dị ứng)"
            },
            "include_ingredients": {
                "type": "ARRAY",
                "items": {"type": "STRING"},
                "description": "Các nguyên liệu người dùng muốn có trong món ăn"
            },
            "analysis_note": {
                "type": "STRING",
                "description": "Giải thích ngắn gọn lý do phân loại (Vd: Người dùng bị dị ứng nên đưa vào cả tag sức khỏe và danh sách loại trừ)"
            }
        },
        "required": ["health_constraints", "exclude_ingredients", "include_ingredients"]
    }

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0, # Để tính nhất quán cao nhất
                response_mime_type="application/json",
                response_schema=response_schema
            ),
            contents=user_input
        )
        return json.loads(response.text)
    except Exception as e:
        return {"error": str(e)}

# --- TEST CASE ---
if __name__ == "__main__":
    test_queries = [
        "Mình khoái và nghiện những món có gà và rau răm hãy gợi ý món."
    ]

    for query in test_queries:
        print(f"\nQuery: {query}")
        output = supervisor_agent(query)
        if output:
            print(json.dumps(output, indent=4, ensure_ascii=False))