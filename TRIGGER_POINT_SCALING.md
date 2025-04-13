# Trigger Point Positioning Guide

## Problem

The trigger points on the body chart weren't always displaying in their correct anatomical locations. In some cases, points appeared outside the visible body area or in incorrect positions compared to where they were originally placed.

## Solution

We've created a solution that maintains the original anatomical positions while ensuring the points are visible on the body chart:

1. A utility script `fix_trigger_point_scaling.py` to adjust any trigger points that fall outside the visible body area
2. Updated templates with the proper SVG viewBox dimensions (500x800) to match the coordinate system used when adding points
3. Clearly defined boundaries to ensure trigger points stay within the visible body outline

## How to Use the Fix Script

### Fix All Treatments

```bash
./fix_trigger_point_scaling.py all
```

This will:

- Back up your database first (in case anything goes wrong)
- Check all treatments with trigger points
- Only adjust points that fall outside the visible body area
- Show a report of all adjustments made

### Fix Individual Treatments

```bash
./fix_trigger_point_scaling.py single <treatment_id>
```

Example:

```bash
./fix_trigger_point_scaling.py single 61
```

### Fix Specific Treatments

```bash
./fix_trigger_point_scaling.py batch 12 15 23
```

## How It Works

The script uses boundary constraints to ensure points are visible without changing their relative anatomical positions:

```python
# Horizontal boundaries - keep points on the body
if x < 150:
    # Left side adjustment (if too far left)
    x = max(150, x)
elif x > 350:
    # Right side adjustment (if too far right)
    x = min(350, x)

# Vertical boundaries - keep points on the body
if y < 80:
    # Top adjustment (if too high)
    y = max(80, y)
elif y > 700:
    # Bottom adjustment (if too low)
    y = min(700, y)
```

## Additional Fixes

We've also updated the following templates to ensure correct trigger point display:

1. `app/templates/treatment_detail.html` - Updated SVG viewBox to 500x800
2. `app/templates/view_treatment.html` - Updated SVG viewBox to 500x800

## Further Improvements

If you still notice positioning issues after running the script, you can:

1. Adjust the boundary values in `fix_trigger_point_scaling.py` based on your specific body chart dimensions
2. Run the script again with the updated boundaries
3. Check that all templates use the same SVG viewBox dimensions (500x800)

---

## Technical Background

### The Position Fixing Algorithm

Our approach preserves the original anatomical positions while ensuring visibility:

```python
def fix_point_position(point):
    """
    Ensure trigger point is visible on the body chart without changing its anatomical position.
    This approach preserves the original relative position while ensuring it's visible on the chart.
    """
    # Get original position
    x = float(point.get("x", 0))
    y = float(point.get("y", 0))

    # Only adjust points that are outside the visible body area
    # These values are specific to the bodychart.svg dimensions

    # Horizontal boundaries - keep points on the body
    if x < 150:
        # Left side adjustment (if too far left)
        x = max(150, x)
    elif x > 350:
        # Right side adjustment (if too far right)
        x = min(350, x)

    # Vertical boundaries - keep points on the body
    if y < 80:
        # Top adjustment (if too high)
        y = max(80, y)
    elif y > 700:
        # Bottom adjustment (if too low)
        y = min(700, y)

    # Return corrected position
    return round(x, 1), round(y, 1)
```

This function:

1. Maintains the original coordinates whenever possible
2. Only adjusts points that would be invisible or misplaced
3. Ensures points remain within the valid boundary of the body chart

---

Created by PhysioApp Support Team
