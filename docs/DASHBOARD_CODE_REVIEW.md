# Dashboard Code Review — Vyapaar MCP

**Reviewed:** `demo/dashboard.py`  
**Reviewer:** Streamlit Best Practices (agent-skills)  
**Date:** 2026-02-15

---

## Summary

The dashboard is functional and well-structured. It demonstrates 6 security scenarios and 9 feature showcases with proper Material icons and border styling. However, there are several performance and best practice issues that should be addressed.

---

## 🚨 Critical Issues

### 1. Health check runs on every interaction

The `check_health()` function is called in the sidebar on every app rerun:

```python
# BAD: Runs on every rerun
health = asyncio.run(check_health())
```

**Fix:** Use `@st.fragment` for auto-refreshing health status, or cache with short TTL:

```python
@st.fragment(run_every="10s")
def health_status():
    health = asyncio.run(check_health())
    # Display badges
```

Or use the cached version already added:

```python
health = get_cached_health()
```

---

### 2. Scenario functions are async but called synchronously

```python
# BAD: Creates new event loop
if st.button(...):
    run_scenario_1()  # This is async but called without await
```

**Fix:** Either use `asyncio.run()` inside the button handler, or refactor to use synchronous patterns:

```python
if st.button(...):
    asyncio.run(run_scenario_1())
```

---

## ⚠️ Warnings

### 3. Missing TTL on config caching

```python
@st.cache_resource
def get_config():
    # This is fine, but could benefit from TTL for development
```

**Suggestion:** Add TTL during development to pick up config changes:

```python
@st.cache_resource(ttl="1h")
def get_config():
    ...
```

---

### 4. Button inside cached function anti-pattern

The showcase functions pass widget values correctly, but the pattern could be cleaner with `st.form`:

```python
# Current: Each button triggers full rerun
url = st.text_input("...")
if st.button("Check"):
    ...

# Better: Use form to batch inputs
with st.form("reputation_form"):
    url = st.text_input("...")
    submitted = st.form_submit_button("Check", type="primary")

if submitted:
    ...
```

---

### 5. Missing `on_release` cleanup for connections

The services are initialized in `session_state` but never cleaned up:

```python
# Should add cleanup
async def cleanup_services():
    if st.session_state.redis:
        await st.session_state.redis.disconnect()
    if st.session_state.postgres:
        await st.session_state.postgres.disconnect()
```

---

## ✅ Good Practices Found

1. **Proper icon usage** — Using Material icons (`:material/shield:`)
2. **Border on metrics** — Using `border=True` on KPI metrics
3. **Horizontal containers** — Using `st.container(horizontal=True)` for responsive KPIs
4. **Expanders** — Hiding detailed JSON in expanders
5. **Session state** — Proper use of `st.session_state` for service objects

---

## 🎯 Recommendations

| Priority | Issue | Fix |
|----------|-------|-----|
| High | Health runs every rerun | Use `@st.fragment(run_every="10s")` |
| High | Async functions not awaited | Wrap in `asyncio.run()` |
| Medium | No form batching | Add `st.form` for input sections |
| Medium | No cleanup on exit | Add `on_exit` handler |
| Low | Config could use TTL | Add `ttl="1h"` during dev |

---

## 📝 Refactored Health Status Example

```python
@st.fragment(run_every="15s")
def health_status():
    """Auto-refreshing health status in sidebar."""
    st.header(":heartpulse: Status")
    
    if not st.session_state.initialized:
        st.warning("Services not initialized")
        return
    
    health = asyncio.run(check_health())
    
    # Status badges
    redis_status = health.get("redis", "unknown")
    if redis_status == "ok":
        st.markdown(":green-badge[Redis: OK]")
    else:
        st.markdown(":red-badge[Redis: Error]")
```

---

## Conclusion

The dashboard is production-ready for a hackathon demo. The main issues are performance-related (health checking) and async handling. For a polished production deployment, address the critical items above.

**Rating:** ⭐⭐⭐⭐☆ (4/5)
