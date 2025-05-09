# tests/test_attack_workflow.py

from workflows.attack_workflow import create_attack_workflow

if __name__ == "__main__":
    graph = create_attack_workflow()
    app = graph.compile()

    print("Workflow Graph (ASCII):")
    print(app.get_graph().draw_ascii())

    # Optional Mermaid diagram (requires graphviz + IPython)
    try:
        from IPython.display import display
        display(app.get_graph().draw_mermaid_png())
    except Exception as e:
        print("Mermaid rendering skipped:", str(e))