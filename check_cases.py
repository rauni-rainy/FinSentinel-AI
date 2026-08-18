import os, psycopg
from dotenv import load_dotenv
from langgraph.checkpoint.postgres import PostgresSaver
from agents.graph import build_investigation_graph

load_dotenv("backend/.env")
load_dotenv(".env")

db_url = os.getenv("DATABASE_URL")

with psycopg.connect(db_url, autocommit=True) as conn:
    cp = PostgresSaver(conn)
    workflow = build_investigation_graph()
    app = workflow.compile(checkpointer=cp)

    try:
        states = list(cp.list(None))
    except Exception as e:
        print(f"list() error: {e}")
        states = []

    print(f"Total states from cp.list(None): {len(states)}")

    seen_threads = set()
    pending = []
    no_tasks = 0
    has_tasks_no_interrupt = 0
    completed = 0

    for s in states[:200]:  # limit scan
        thread_id = s.config["configurable"]["thread_id"]
        if thread_id in seen_threads:
            continue
        seen_threads.add(thread_id)

        try:
            snapshot = app.get_state({"configurable": {"thread_id": thread_id}})
            if not snapshot.tasks:
                no_tasks += 1
            elif not any(t.interrupts for t in snapshot.tasks):
                has_tasks_no_interrupt += 1
                completed += 1
            else:
                pending.append(thread_id)
        except Exception as e:
            print(f"  Error on {thread_id}: {e}")
            continue

    print(f"Distinct threads scanned: {len(seen_threads)}")
    print(f"  - No tasks (completed/terminal): {no_tasks}")
    print(f"  - Tasks but no interrupt: {has_tasks_no_interrupt}")
    print(f"  - Pending (has interrupt): {len(pending)}")
    if pending:
        print(f"\nSample pending thread: {pending[0]}")
        snap = app.get_state({"configurable": {"thread_id": pending[0]}})
        print(f"  tasks: {snap.tasks}")
        print(f"  next: {snap.next}")
        print(f"  values keys: {list(snap.values.keys())}")
