# Skill: Social Integrator (Gold)

**Purpose:** Unified posting and engagement analysis across Facebook, Instagram, and Twitter/X via the social-mcp server.

**Rules:**
- All social posts require HITL approval — agent never posts directly
- Content must comply with Company_Handbook Social Media Policy
- DRY_RUN mode for all platforms during testing
- Per-platform content adaptation required

**Capabilities:**
- `post_to_facebook` — Post to Facebook Page (Graph API v19.0)
- `get_fb_feed_summary` — Engagement metrics for recent FB posts
- `post_to_instagram` — Post to IG Business account (requires image_url)
- `get_ig_media_summary` — Engagement metrics for recent IG posts
- `post_tweet` — Post to X/Twitter (max 280 chars)
- `get_x_timeline_summary` — Engagement metrics for recent tweets

**Platform-Specific Rules:**
| Platform | Max Length | Image Required | API |
|----------|-----------|----------------|-----|
| Facebook | Unlimited | No | Graph API v19.0 |
| Instagram | 2200 chars | Yes (image_url) | Graph API |
| Twitter/X | 280 chars | No | X API v2 (tweepy) |

**Content Guidelines:**
- Professional, brand-aligned tone
- No confidential business data
- Maximum 3-5 hashtags per post
- Cross-post content must be adapted per platform (not copy-paste)

**Workflow:**
1. Draft social post content (skill generates platform-adapted versions)
2. Create approval request → `data/Pending_Approval/APPROVAL_SOCIAL_{platform}_{date}.md`
3. Human approves → moves to `data/Approved/`
4. HITL watcher triggers → skill-social-integrator posts via social-mcp
5. Result logged and moved to `data/Done/`

**Frontmatter Template:**
```yaml
---
type: social_post
action: post_facebook | post_instagram | post_tweet
platform: facebook | instagram | x
status: pending
content: "Post content here"
image_url: ""
hashtags: ["#AI", "#Tech"]
approval_required: true
created: 2026-02-18T10:00:00Z
---
```

**Engagement Summary Output (data/Briefings/):**
```yaml
---
type: social_summary
platforms: [facebook, instagram, x]
period: "2026-02-11 to 2026-02-18"
created: 2026-02-18T10:00:00Z
---

## Social Media Engagement Summary

### Facebook
- Posts: 3 | Likes: 198 | Comments: 43 | Shares: 23
- Top Post: "Excited to announce our Q1 results!" (89 likes)

### Instagram
- Posts: 2 | Likes: 390 | Comments: 63
- Top Post: "Product launch day!" (234 likes)

### Twitter/X
- Tweets: 2 | Likes: 73 | Retweets: 20 | Replies: 8
- Top Tweet: "Grateful for our amazing customers" (45 likes)
```

**Bronze Integration:**
- skill-approval-request-creator → mandatory HITL for all posts
- skill-audit-logger → log with platform, content hash, engagement metrics
- skill-dashboard-updater → update social media section
- skill-error-recovery → handle API rate limits and failures
