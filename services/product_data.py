import json
import math
import config


def load_products() -> dict:
    """載入 products.json"""
    with open(config.PRODUCTS_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def get_product_models(products: dict) -> list[str]:
    """取得所有產品型號，排序"""
    return sorted(products.keys())


def get_packing_options(products: dict, model: str) -> list[dict]:
    """取得指定型號的所有包裝規格"""
    return products.get(model, [])


def calculate_shipment(packing_option: dict, quantity_sets: int) -> dict:
    """
    計算箱數和總重量

    Args:
        packing_option: {"sets_per_carton": 3, "weight_kg": 9.33}
        quantity_sets: 業務輸入的組數

    Returns:
        {"num_cartons": 10, "total_weight_kg": 93.3}
    """
    sets_per_carton = packing_option["sets_per_carton"]
    weight_per_carton = packing_option["weight_kg"]

    num_cartons = math.ceil(quantity_sets / sets_per_carton)
    total_weight = round(num_cartons * weight_per_carton, 2)

    return {
        "num_cartons": num_cartons,
        "total_weight_kg": total_weight,
    }


def format_packing_label(option: dict) -> str:
    """格式化包裝規格顯示文字"""
    return f"{option['sets_per_carton']} sets/箱, 每箱 {option['weight_kg']} kg"
