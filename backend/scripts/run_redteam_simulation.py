import os
import sys
import json
import uuid
import datetime
import psycopg

# Ensure backend directory is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.graph import build_investigation_graph
from langgraph.checkpoint.postgres import PostgresSaver
from langchain_core.messages import HumanMessage

def run_simulation():
    db_url = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/finsentinel")
    
    structuring_variants = [
        {"id": "V1", "name": "Baseline (1x $30k)", "amount": 30000.00, "merchant_category": "electronics", "merchant_id": "merch_bigbox", "account_id": "rt_struct_01"},
        {"id": "V2", "name": "Basic Split (3x $10k)", "amount": 10000.00, "merchant_category": "electronics", "merchant_id": "merch_bigbox", "account_id": "rt_struct_01"},
        {"id": "V3", "name": "Sub-Reporting (6x $5k)", "amount": 5000.00, "merchant_category": "electronics", "merchant_id": "merch_bigbox", "account_id": "rt_struct_01"},
        {"id": "V4", "name": "Micro-Structuring (15x $2k)", "amount": 2000.00, "merchant_category": "electronics", "merchant_id": "merch_bigbox", "account_id": "rt_struct_01"},
        {"id": "V5", "name": "Drip Fraud (30x $1k)", "amount": 1000.00, "merchant_category": "electronics", "merchant_id": "merch_bigbox", "account_id": "rt_struct_01"}
    ]
    
    synthetic_id_variants = [
        {"id": "V1", "name": "Known Fraud ID", "amount": 15000.00, "merchant_category": "crypto", "merchant_id": "merch_crypto_1", "account_id": "known_fraud_99", "device_id": "dev_bad_123"},
        {"id": "V2", "name": "Burner Device", "amount": 15000.00, "merchant_category": "crypto", "merchant_id": "merch_crypto_1", "account_id": "known_fraud_99", "device_id": "dev_new_456"},
        {"id": "V3", "name": "Mixed Account ID", "amount": 15000.00, "merchant_category": "crypto", "merchant_id": "merch_crypto_1", "account_id": "syn_new_789", "device_id": "dev_new_456"},
        {"id": "V4", "name": "Retail Wash", "amount": 15000.00, "merchant_category": "retail", "merchant_id": "merch_retail_1", "account_id": "syn_new_789", "device_id": "dev_new_456"},
        {"id": "V5", "name": "Full Synthetic Wash", "amount": 250.00, "merchant_category": "groceries", "merchant_id": "merch_grocery", "account_id": "syn_new_789", "device_id": "dev_new_456"}
    ]
    
    results = {
        "metadata": {
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "model": "phi4-mini",
            "embeddings": "nomic-embed-text"
        },
        "scenarios": [
            {
                "id": "structuring",
                "name": "Structuring / Smurfing",
                "description": "Progressively splitting a $30k fraudulent transfer to evade fast-path rules.",
                "variants": []
            },
            {
                "id": "synthetic_id",
                "name": "Synthetic Identity Evasion",
                "description": "Progressively blending identity signals to evade historical vector matching.",
                "variants": []
            }
        ]
    }
    
    print("Starting Adversarial Red-Team Simulator...", flush=True)
    print(f"Connecting to DB: {db_url}", flush=True)
    
    with psycopg.connect(db_url, autocommit=True) as conn:
        cp = PostgresSaver(conn)
        # Create tables if they don't exist
        cp.setup()
        workflow = build_investigation_graph()
        app = workflow.compile(checkpointer=cp)
        
        # Run Structuring
        print("\n--- Running Structuring Scenario ---", flush=True)
        for idx, variant in enumerate(structuring_variants):
            print(f"Processing Variant {variant['id']} ({variant['name']})...", flush=True)
            thread_id = f"rt_struct_{uuid.uuid4()}"
            config = {"configurable": {"thread_id": thread_id}}
            
            initial_state = {
                "transaction": {
                    "transaction_id": f"txn_struct_{idx}",
                    "account_id": variant["account_id"],
                    "amount": variant["amount"],
                    "merchant_category": variant["merchant_category"],
                    "merchant_id": variant["merchant_id"]
                },
                "retrieved_similar_cases": [],
                "investigation_notes": {},
                "risk_score": 0.0,
                "calibrated_confidence": 0.0,
                "recommended_action": "PENDING"
            }
            
            # Execute graph
            for _ in app.stream(initial_state, config=config):
                pass
                
            final_state = app.get_state(config).values
            
            results["scenarios"][0]["variants"].append({
                "variant_id": variant["id"],
                "name": variant["name"],
                "inputs": variant,
                "risk_score": final_state.get("risk_score", 0.0),
                "calibrated_confidence": final_state.get("calibrated_confidence", 0.0),
                "recommended_action": final_state.get("recommended_action", "UNKNOWN"),
                "llm_reasoning": final_state.get("investigation_notes", {})
            })

        # Run Synthetic Identity
        print("\n--- Running Synthetic Identity Scenario ---")
        for idx, variant in enumerate(synthetic_id_variants):
            print(f"Processing Variant {variant['id']} ({variant['name']})...")
            thread_id = f"rt_syn_{uuid.uuid4()}"
            config = {"configurable": {"thread_id": thread_id}}
            
            initial_state = {
                "transaction": {
                    "transaction_id": f"txn_syn_{idx}",
                    "account_id": variant["account_id"],
                    "amount": variant["amount"],
                    "merchant_category": variant["merchant_category"],
                    "merchant_id": variant["merchant_id"],
                    "device_id": variant.get("device_id", "")
                },
                "retrieved_similar_cases": [],
                "investigation_notes": {},
                "risk_score": 0.0,
                "calibrated_confidence": 0.0,
                "recommended_action": "PENDING"
            }
            
            for _ in app.stream(initial_state, config=config):
                pass
                
            final_state = app.get_state(config).values
            
            results["scenarios"][1]["variants"].append({
                "variant_id": variant["id"],
                "name": variant["name"],
                "inputs": variant,
                "risk_score": final_state.get("risk_score", 0.0),
                "calibrated_confidence": final_state.get("calibrated_confidence", 0.0),
                "recommended_action": final_state.get("recommended_action", "UNKNOWN"),
                "llm_reasoning": final_state.get("investigation_notes", {})
            })
            
    # Write output to static directory
    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "reports", "redteam")
    os.makedirs(output_dir, exist_ok=True)
    
    timestamp_str = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    file_path = os.path.join(output_dir, f"redteam_results_{timestamp_str}.json")
    
    with open(file_path, "w") as f:
        json.dump(results, f, indent=2)
        
    print(f"\nSimulation Complete. Artifact written to: {file_path}")

if __name__ == "__main__":
    run_simulation()
