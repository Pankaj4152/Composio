"""Canonical source list for the 100-app research set.

This module preserves the assignment's app names, category labels, ordering,
and supplied hints. A hint is intentionally stored as text rather than a
validated URL: a few assignment hints are not URLs (for example, Paygent).
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AppEntry:
    """One app from the fixed research assignment."""

    id: int
    name: str
    category: str
    hint: str


CATEGORIES: tuple[str, ...] = (
    "CRM and Sales",
    "Support and Helpdesk",
    "Communications and Messaging",
    "Marketing, Ads, Email and Social",
    "Ecommerce",
    "Data, SEO and Scraping",
    "Developer, Infra and Data platforms",
    "Productivity and Project Management",
    "Finance and Fintech",
    "AI, Research and Media-native",
)


APPS: tuple[AppEntry, ...] = (
    # 1. CRM and Sales
    AppEntry(1, "Salesforce", "CRM and Sales", "salesforce.com"),
    AppEntry(2, "HubSpot", "CRM and Sales", "hubspot.com"),
    AppEntry(3, "Pipedrive", "CRM and Sales", "pipedrive.com"),
    AppEntry(4, "Attio", "CRM and Sales", "attio.com"),
    AppEntry(5, "Twenty", "CRM and Sales", "twenty.com (open-source CRM)"),
    AppEntry(6, "Podio", "CRM and Sales", "podio.com"),
    AppEntry(7, "Zoho CRM", "CRM and Sales", "zoho.com/crm"),
    AppEntry(8, "Close", "CRM and Sales", "close.com"),
    AppEntry(9, "Copper", "CRM and Sales", "copper.com"),
    AppEntry(10, "DealCloud", "CRM and Sales", "api.docs.dealcloud.com"),
    # 2. Support and Helpdesk
    AppEntry(11, "Zendesk", "Support and Helpdesk", "zendesk.com"),
    AppEntry(12, "Intercom", "Support and Helpdesk", "intercom.com"),
    AppEntry(13, "Freshdesk", "Support and Helpdesk", "freshdesk.com"),
    AppEntry(14, "Front", "Support and Helpdesk", "front.com"),
    AppEntry(15, "Pylon", "Support and Helpdesk", "usepylon.com"),
    AppEntry(16, "LiveAgent", "Support and Helpdesk", "liveagent.com"),
    AppEntry(17, "Plain", "Support and Helpdesk", "plain.com"),
    AppEntry(18, "Help Scout", "Support and Helpdesk", "helpscout.com"),
    AppEntry(19, "Gorgias", "Support and Helpdesk", "gorgias.com"),
    AppEntry(20, "Gladly", "Support and Helpdesk", "gladly.com"),
    # 3. Communications and Messaging
    AppEntry(21, "Slack", "Communications and Messaging", "slack.com"),
    AppEntry(22, "Twilio", "Communications and Messaging", "twilio.com"),
    AppEntry(23, "Zoho Cliq", "Communications and Messaging", "zoho.com/cliq"),
    AppEntry(24, "Lark (Larksuite)", "Communications and Messaging", "open.larksuite.com"),
    AppEntry(25, "Pumble", "Communications and Messaging", "pumble.com"),
    AppEntry(26, "Discord", "Communications and Messaging", "discord.com"),
    AppEntry(27, "Telegram", "Communications and Messaging", "core.telegram.org"),
    AppEntry(28, "WhatsApp Business", "Communications and Messaging", "developers.facebook.com/docs/whatsapp"),
    AppEntry(29, "Aircall", "Communications and Messaging", "aircall.io"),
    AppEntry(30, "Vonage", "Communications and Messaging", "developer.vonage.com"),
    # 4. Marketing, Ads, Email and Social
    AppEntry(31, "Google Ads", "Marketing, Ads, Email and Social", "developers.google.com/google-ads"),
    AppEntry(32, "Meta Ads", "Marketing, Ads, Email and Social", "developers.facebook.com/docs/marketing-apis"),
    AppEntry(33, "LinkedIn Ads", "Marketing, Ads, Email and Social", "learn.microsoft.com/linkedin/marketing"),
    AppEntry(34, "GoHighLevel", "Marketing, Ads, Email and Social", "highlevel.stoplight.io"),
    AppEntry(35, "Mailchimp", "Marketing, Ads, Email and Social", "mailchimp.com/developer"),
    AppEntry(36, "Klaviyo", "Marketing, Ads, Email and Social", "developers.klaviyo.com"),
    AppEntry(37, "systeme.io", "Marketing, Ads, Email and Social", "systeme.io (funnel builder)"),
    AppEntry(38, "Pinterest", "Marketing, Ads, Email and Social", "developers.pinterest.com"),
    AppEntry(39, "Threads (Meta)", "Marketing, Ads, Email and Social", "developers.facebook.com/docs/threads"),
    AppEntry(40, "SendGrid", "Marketing, Ads, Email and Social", "sendgrid.com"),
    # 5. Ecommerce
    AppEntry(41, "Shopify", "Ecommerce", "shopify.dev"),
    AppEntry(42, "WooCommerce", "Ecommerce", "woocommerce.com/document/woocommerce-rest-api"),
    AppEntry(43, "BigCommerce", "Ecommerce", "developer.bigcommerce.com"),
    AppEntry(44, "Salesforce Commerce Cloud", "Ecommerce", "developer.salesforce.com/docs/commerce"),
    AppEntry(45, "Magento (Adobe Commerce)", "Ecommerce", "developer.adobe.com/commerce"),
    AppEntry(46, "Squarespace", "Ecommerce", "developers.squarespace.com"),
    AppEntry(47, "Ecwid", "Ecommerce", "api-docs.ecwid.com"),
    AppEntry(48, "Gumroad", "Ecommerce", "gumroad.com/api"),
    AppEntry(49, "Amazon Selling Partner", "Ecommerce", "developer-docs.amazon.com/sp-api"),
    AppEntry(50, "fanbasis", "Ecommerce", "fanbasis.com"),
    # 6. Data, SEO and Scraping
    AppEntry(51, "DataForSEO", "Data, SEO and Scraping", "docs.dataforseo.com"),
    AppEntry(52, "SE Ranking", "Data, SEO and Scraping", "seranking.com/api"),
    AppEntry(53, "Ahrefs", "Data, SEO and Scraping", "ahrefs.com/api"),
    AppEntry(54, "MrScraper", "Data, SEO and Scraping", "docs.mrscraper.com"),
    AppEntry(55, "Apify", "Data, SEO and Scraping", "docs.apify.com"),
    AppEntry(56, "Firecrawl", "Data, SEO and Scraping", "firecrawl.dev"),
    AppEntry(57, "Bright Data", "Data, SEO and Scraping", "brightdata.com"),
    AppEntry(58, "Sherlock", "Data, SEO and Scraping", "github.com/sherlock-project/sherlock"),
    AppEntry(59, "Waterfall.io", "Data, SEO and Scraping", "waterfall.io (contact/company intel)"),
    AppEntry(60, "Clay", "Data, SEO and Scraping", "clay.com"),
    # 7. Developer, Infra and Data platforms
    AppEntry(61, "GitHub", "Developer, Infra and Data platforms", "docs.github.com/rest"),
    AppEntry(62, "Vercel", "Developer, Infra and Data platforms", "vercel.com/docs/rest-api"),
    AppEntry(63, "Netlify", "Developer, Infra and Data platforms", "docs.netlify.com/api"),
    AppEntry(64, "Cloudflare", "Developer, Infra and Data platforms", "developers.cloudflare.com/api"),
    AppEntry(65, "Supabase", "Developer, Infra and Data platforms", "supabase.com/docs"),
    AppEntry(66, "Neo4j", "Developer, Infra and Data platforms", "neo4j.com/docs/api"),
    AppEntry(67, "Snowflake", "Developer, Infra and Data platforms", "docs.snowflake.com"),
    AppEntry(68, "MongoDB Atlas", "Developer, Infra and Data platforms", "mongodb.com/docs/atlas/api"),
    AppEntry(69, "Datadog", "Developer, Infra and Data platforms", "docs.datadoghq.com/api"),
    AppEntry(70, "Sentry", "Developer, Infra and Data platforms", "docs.sentry.io/api"),
    # 8. Productivity and Project Management
    AppEntry(71, "Notion", "Productivity and Project Management", "developers.notion.com"),
    AppEntry(72, "Airtable", "Productivity and Project Management", "airtable.com/developers"),
    AppEntry(73, "Linear", "Productivity and Project Management", "developers.linear.app"),
    AppEntry(74, "Jira", "Productivity and Project Management", "developer.atlassian.com"),
    AppEntry(75, "Asana", "Productivity and Project Management", "developers.asana.com"),
    AppEntry(76, "Monday.com", "Productivity and Project Management", "developer.monday.com"),
    AppEntry(77, "ClickUp", "Productivity and Project Management", "clickup.com/api"),
    AppEntry(78, "Coda", "Productivity and Project Management", "coda.io/developers"),
    AppEntry(79, "Smartsheet", "Productivity and Project Management", "smartsheet.com/developers"),
    AppEntry(80, "Harvest", "Productivity and Project Management", "help.getharvest.com/api-v2"),
    # 9. Finance and Fintech
    AppEntry(81, "Stripe", "Finance and Fintech", "stripe.com/docs/api"),
    AppEntry(82, "Plaid", "Finance and Fintech", "plaid.com/docs"),
    AppEntry(83, "Binance", "Finance and Fintech", "binance-docs.github.io"),
    AppEntry(84, "Paygent Connect", "Finance and Fintech", "paygent (NMI-powered)"),
    AppEntry(85, "iPayX", "Finance and Fintech", "ipayx.ai/docs"),
    AppEntry(86, "QuickBooks", "Finance and Fintech", "developer.intuit.com"),
    AppEntry(87, "Xero", "Finance and Fintech", "developer.xero.com"),
    AppEntry(88, "Brex", "Finance and Fintech", "developer.brex.com"),
    AppEntry(89, "Ramp", "Finance and Fintech", "docs.ramp.com"),
    AppEntry(90, "PitchBook", "Finance and Fintech", "pitchbook.com (research API)"),
    # 10. AI, Research and Media-native
    AppEntry(91, "NotebookLM", "AI, Research and Media-native", "cloud.google.com/gemini (Enterprise API)"),
    AppEntry(92, "Otter AI", "AI, Research and Media-native", "help.otter.ai (MCP server)"),
    AppEntry(93, "Fathom", "AI, Research and Media-native", "fathom.video"),
    AppEntry(94, "Consensus", "AI, Research and Media-native", "consensus.app (OAuth requested)"),
    AppEntry(95, "Reducto", "AI, Research and Media-native", "reducto.ai (document parsing)"),
    AppEntry(96, "Devin", "AI, Research and Media-native", "docs.devin.ai (MCP)"),
    AppEntry(97, "higgsfield", "AI, Research and Media-native", "higgsfield.ai/cli (content suite)"),
    AppEntry(98, "Mermaid CLI", "AI, Research and Media-native", "github.com/mermaid-js/mermaid-cli"),
    AppEntry(99, "YouTube Transcript", "AI, Research and Media-native", "transcriptapi.com"),
    AppEntry(100, "Grain", "AI, Research and Media-native", "grain.com (meeting notes)"),
)
