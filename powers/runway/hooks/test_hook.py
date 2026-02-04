"""
Simple test hook to verify CFNgin hook loading works.
"""

def cfngin_hook(context, provider, **kwargs):
    """
    Simple test hook that just returns success.
    """
    print("Test hook executed successfully!")
    return {"status": "success"}
