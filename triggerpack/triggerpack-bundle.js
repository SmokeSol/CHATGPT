// Generated from the tested TriggerPack repository.
import * as __ext_node_crypto from "node:crypto";
import * as __ext_node_net from "node:net";
import * as __ext_zod from "npm:zod@3.24.2";
import * as __ext_hono from "npm:hono@4.9.8";
import * as __ext_x402_hono from "npm:@x402/hono@2.23.0";
import * as __ext_x402_core_server from "npm:@x402/core@2.23.0/server";
import * as __ext_x402_evm_server from "npm:@x402/evm@2.23.0/exact/server";

const __externals = {
  "node:crypto": __ext_node_crypto,
  "node:net": __ext_node_net,
  "npm:zod@3.24.2": __ext_zod,
  "npm:hono@4.9.8": __ext_hono,
  "npm:@x402/hono@2.23.0": __ext_x402_hono,
  "npm:@x402/core@2.23.0/server": __ext_x402_core_server,
  "npm:@x402/evm@2.23.0/exact/server": __ext_x402_evm_server,
};
const __modules = Object.create(null);
const __cache = Object.create(null);
function __normalize(parts) { const stack=[]; for (const part of parts) { if (!part || part === '.') continue; if (part === '..') stack.pop(); else stack.push(part); } return '/' + stack.join('/'); }
function __resolve(from, id) { if (!id.startsWith('.')) return id; const base=from.split('/').slice(0,-1); let resolved=__normalize([...base, ...id.split('/')]); if (!/\.[cm]?[jt]s$/.test(resolved)) resolved += '.ts'; return resolved; }
function __require(from, id) { const resolved=__resolve(from,id); if (!resolved.startsWith('/')) { if (!(resolved in __externals)) throw new Error('Unknown external module: '+resolved); return __externals[resolved]; } if (__cache[resolved]) return __cache[resolved].exports; const factory=__modules[resolved]; if (!factory) throw new Error('Unknown local module: '+resolved+' from '+from); const module={exports:{}}; __cache[resolved]=module; factory(module,module.exports,(next)=>__require(resolved,next)); return module.exports; }

__modules["/types.ts"] = function(module, exports, require) {
"use strict";
Object.defineProperty(exports, "__esModule", { value: true });

};

__modules["/cache.ts"] = function(module, exports, require) {
"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.TtlLru = void 0;
class TtlLru {
    values = new Map();
    maxEntries;
    defaultTtlMs;
    constructor(maxEntries, defaultTtlMs) {
        if (!Number.isInteger(maxEntries) || maxEntries < 1)
            throw new Error("maxEntries must be positive");
        if (!Number.isFinite(defaultTtlMs) || defaultTtlMs <= 0)
            throw new Error("defaultTtlMs must be positive");
        this.maxEntries = maxEntries;
        this.defaultTtlMs = defaultTtlMs;
    }
    get(key, now = Date.now()) {
        const entry = this.values.get(key);
        if (!entry)
            return undefined;
        if (entry.expiresAt <= now) {
            this.values.delete(key);
            return undefined;
        }
        this.values.delete(key);
        this.values.set(key, entry);
        return entry.value;
    }
    set(key, value, ttlMs = this.defaultTtlMs, now = Date.now()) {
        this.values.delete(key);
        this.values.set(key, { value, expiresAt: now + ttlMs });
        while (this.values.size > this.maxEntries) {
            const oldest = this.values.keys().next().value;
            if (oldest === undefined)
                break;
            this.values.delete(oldest);
        }
    }
    delete(key) {
        this.values.delete(key);
    }
    clear() {
        this.values.clear();
    }
    get size() {
        return this.values.size;
    }
}
exports.TtlLru = TtlLru;

};

__modules["/domain.ts"] = function(module, exports, require) {
"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.normalizeCompanyDomain = normalizeCompanyDomain;
exports.registrableDomain = registrableDomain;
exports.isSameCompanyDomain = isSameCompanyDomain;
exports.isForbiddenHostname = isForbiddenHostname;
exports.isForbiddenIp = isForbiddenIp;
exports.canonicalizeHttpUrl = canonicalizeHttpUrl;
const node_net_1 = require("node:net");
const COMMON_SECOND_LEVEL_SUFFIXES = new Set([
    "co.uk",
    "org.uk",
    "ac.uk",
    "com.au",
    "net.au",
    "org.au",
    "co.nz",
    "com.br",
    "com.mx",
    "co.jp",
    "co.kr",
    "com.sg",
    "com.hk",
    "co.in",
    "co.za",
    "com.cn",
    "com.tw",
    "com.tr",
    "com.sa",
    "com.ar",
    "com.co",
]);
function normalizeCompanyDomain(input) {
    const raw = input.trim();
    if (!raw)
        throw new Error("company_domain is required");
    if (raw.length > 253)
        throw new Error("company_domain is too long");
    const withProtocol = /^[a-z][a-z0-9+.-]*:\/\//i.test(raw)
        ? raw
        : `https://${raw}`;
    let parsed;
    try {
        parsed = new URL(withProtocol);
    }
    catch {
        throw new Error("company_domain must be a valid public domain or HTTP(S) URL");
    }
    if (parsed.protocol !== "https:" && parsed.protocol !== "http:") {
        throw new Error("only HTTP(S) company domains are supported");
    }
    if (parsed.username || parsed.password) {
        throw new Error("credential-bearing URLs are not allowed");
    }
    if (parsed.port && parsed.port !== "80" && parsed.port !== "443") {
        throw new Error("custom ports are not allowed");
    }
    let hostname = parsed.hostname.toLowerCase().replace(/\.$/, "");
    if (hostname.startsWith("www."))
        hostname = hostname.slice(4);
    if (!hostname.includes("."))
        throw new Error("a public company domain is required");
    if (hostname.includes(".."))
        throw new Error("invalid domain");
    if (!/^[a-z0-9.-]+$/i.test(hostname))
        throw new Error("invalid domain characters");
    if ((0, node_net_1.isIP)(hostname) !== 0)
        throw new Error("raw IP addresses are not accepted as company domains");
    if (isForbiddenHostname(hostname))
        throw new Error("private or reserved hostnames are not allowed");
    return hostname;
}
function registrableDomain(hostname) {
    const normalized = hostname.toLowerCase().replace(/\.$/, "");
    const parts = normalized.split(".").filter(Boolean);
    if (parts.length <= 2)
        return normalized;
    const lastTwo = parts.slice(-2).join(".");
    if (COMMON_SECOND_LEVEL_SUFFIXES.has(lastTwo) && parts.length >= 3) {
        return parts.slice(-3).join(".");
    }
    return lastTwo;
}
function isSameCompanyDomain(candidateHostname, companyDomain) {
    const candidate = registrableDomain(candidateHostname);
    const company = registrableDomain(companyDomain);
    return candidate === company;
}
function isForbiddenHostname(hostname) {
    const value = hostname.toLowerCase().replace(/\.$/, "");
    return (value === "localhost" ||
        value.endsWith(".localhost") ||
        value.endsWith(".local") ||
        value.endsWith(".internal") ||
        value.endsWith(".home") ||
        value === "metadata.google.internal" ||
        value === "metadata");
}
function parseIpv4(address) {
    const parts = address.split(".");
    if (parts.length !== 4)
        return null;
    const bytes = parts.map((part) => Number(part));
    if (bytes.some((part) => !Number.isInteger(part) || part < 0 || part > 255))
        return null;
    return bytes;
}
function isForbiddenIp(address) {
    const version = (0, node_net_1.isIP)(address);
    if (version === 4) {
        const bytes = parseIpv4(address);
        if (!bytes)
            return true;
        const [a, b] = bytes;
        return (a === 0 ||
            a === 10 ||
            a === 127 ||
            (a === 100 && b >= 64 && b <= 127) ||
            (a === 169 && b === 254) ||
            (a === 172 && b >= 16 && b <= 31) ||
            (a === 192 && b === 0) ||
            (a === 192 && b === 168) ||
            (a === 198 && (b === 18 || b === 19 || b === 51)) ||
            (a === 203 && b === 0) ||
            a >= 224);
    }
    if (version === 6) {
        const value = address.toLowerCase();
        if (value === "::" || value === "::1")
            return true;
        if (value.startsWith("fc") || value.startsWith("fd"))
            return true;
        if (/^fe[89ab]/.test(value))
            return true;
        if (value.startsWith("ff"))
            return true;
        if (value.startsWith("2001:db8:"))
            return true;
        if (value.startsWith("::ffff:")) {
            const mapped = value.slice("::ffff:".length);
            return isForbiddenIp(mapped);
        }
        return false;
    }
    return true;
}
function canonicalizeHttpUrl(raw, base) {
    let parsed;
    try {
        parsed = base ? new URL(raw, base) : new URL(raw);
    }
    catch {
        throw new Error("invalid URL");
    }
    if (parsed.protocol !== "https:" && parsed.protocol !== "http:") {
        throw new Error("only HTTP(S) URLs are allowed");
    }
    if (parsed.username || parsed.password)
        throw new Error("credential-bearing URLs are not allowed");
    if (parsed.port && parsed.port !== "80" && parsed.port !== "443") {
        throw new Error("custom ports are not allowed");
    }
    if (isForbiddenHostname(parsed.hostname))
        throw new Error("forbidden hostname");
    parsed.hash = "";
    return parsed;
}

};

__modules["/http.ts"] = function(module, exports, require) {
"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.DEFAULT_FETCH_POLICY = void 0;
exports.clearFetchCache = clearFetchCache;
exports.resolvePublicAddresses = resolvePublicAddresses;
exports.fetchTextSafe = fetchTextSafe;
exports.fetchJsonSafe = fetchJsonSafe;
exports.mapWithConcurrency = mapWithConcurrency;
const domain_ts_1 = require("./domain.ts");
const cache_ts_1 = require("./cache.ts");
exports.DEFAULT_FETCH_POLICY = {
    timeoutMs: 4_000,
    maxBytes: 2_000_000,
    maxRedirects: 3,
    userAgent: "TriggerPack/0.1 (+https://github.com/SmokeSol/Build_radar_tryout_3)",
};
const responseCache = new cache_ts_1.TtlLru(128, 10 * 60_000);
function clearFetchCache() {
    responseCache.clear();
}
async function resolveDnsType(hostname, type) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 2_000);
    try {
        const url = new URL("https://cloudflare-dns.com/dns-query");
        url.searchParams.set("name", hostname);
        url.searchParams.set("type", type);
        const response = await fetch(url, {
            signal: controller.signal,
            headers: { accept: "application/dns-json", "user-agent": exports.DEFAULT_FETCH_POLICY.userAgent },
        });
        if (!response.ok)
            return [];
        const data = await response.json();
        if (data.Status !== 0)
            return [];
        const wanted = type === "A" ? 1 : 28;
        return (data.Answer ?? [])
            .filter((answer) => answer.type === wanted && typeof answer.data === "string")
            .map((answer) => answer.data.trim());
    }
    catch {
        return [];
    }
    finally {
        clearTimeout(timeout);
    }
}
async function resolvePublicAddresses(hostname) {
    const [ipv4, ipv6] = await Promise.all([
        resolveDnsType(hostname, "A"),
        resolveDnsType(hostname, "AAAA"),
    ]);
    const addresses = [...new Set([...ipv4, ...ipv6])];
    if (addresses.length === 0)
        throw new Error("hostname did not resolve through public DNS");
    const forbidden = addresses.find((address) => (0, domain_ts_1.isForbiddenIp)(address));
    if (forbidden)
        throw new Error("hostname resolved to a forbidden address");
    return addresses;
}
async function readBoundedBody(response, maxBytes) {
    const contentLength = Number(response.headers.get("content-length") ?? "0");
    if (Number.isFinite(contentLength) && contentLength > maxBytes) {
        throw new Error(`response exceeds ${maxBytes} bytes`);
    }
    if (!response.body)
        return "";
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let bytes = 0;
    let output = "";
    while (true) {
        const { done, value } = await reader.read();
        if (done)
            break;
        bytes += value.byteLength;
        if (bytes > maxBytes) {
            await reader.cancel("response too large");
            throw new Error(`response exceeds ${maxBytes} bytes`);
        }
        output += decoder.decode(value, { stream: true });
    }
    output += decoder.decode();
    return output;
}
async function fetchTextSafe(rawUrl, options = {}) {
    const policy = { ...exports.DEFAULT_FETCH_POLICY, ...options.policy };
    let current = (0, domain_ts_1.canonicalizeHttpUrl)(rawUrl);
    const useCache = options.cache ?? !options.headers;
    const cacheKey = current.toString();
    const cached = useCache ? responseCache.get(cacheKey) : undefined;
    if (cached)
        return { ...cached, headers: new Headers(cached.headers) };
    for (let redirectCount = 0; redirectCount <= policy.maxRedirects; redirectCount += 1) {
        await resolvePublicAddresses(current.hostname);
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), policy.timeoutMs);
        let response;
        try {
            response = await fetch(current, {
                method: "GET",
                redirect: "manual",
                signal: controller.signal,
                headers: {
                    accept: "text/html,application/xhtml+xml,application/xml,text/xml,application/json;q=0.9,*/*;q=0.5",
                    "accept-encoding": "identity",
                    "user-agent": policy.userAgent,
                    ...options.headers,
                },
            });
        }
        catch (error) {
            throw new Error(error instanceof DOMException && error.name === "AbortError"
                ? "upstream request timed out"
                : `upstream fetch failed: ${error instanceof Error ? error.message : String(error)}`);
        }
        finally {
            clearTimeout(timeout);
        }
        if ([301, 302, 303, 307, 308].includes(response.status)) {
            const location = response.headers.get("location");
            if (!location)
                throw new Error("redirect missing Location header");
            if (redirectCount >= policy.maxRedirects)
                throw new Error("too many redirects");
            current = (0, domain_ts_1.canonicalizeHttpUrl)(location, current.toString());
            continue;
        }
        const result = {
            url: current.toString(),
            status: response.status,
            contentType: response.headers.get("content-type") ?? "",
            text: await readBoundedBody(response, policy.maxBytes),
            headers: new Headers(response.headers),
        };
        if (useCache && response.status >= 200 && response.status < 300)
            responseCache.set(cacheKey, result);
        return result;
    }
    throw new Error("redirect policy exhausted");
}
async function fetchJsonSafe(rawUrl, options = {}) {
    const response = await fetchTextSafe(rawUrl, options);
    if (response.status < 200 || response.status >= 300)
        throw new Error(`upstream returned HTTP ${response.status}`);
    try {
        return { url: response.url, status: response.status, data: JSON.parse(response.text) };
    }
    catch {
        throw new Error("upstream returned invalid JSON");
    }
}
async function mapWithConcurrency(values, limit, worker) {
    if (values.length === 0)
        return [];
    const results = new Array(values.length);
    let cursor = 0;
    async function run() {
        while (true) {
            const index = cursor;
            cursor += 1;
            if (index >= values.length)
                return;
            results[index] = await worker(values[index], index);
        }
    }
    await Promise.all(Array.from({ length: Math.min(Math.max(1, limit), values.length) }, () => run()));
    return results;
}

};

__modules["/html.ts"] = function(module, exports, require) {
"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.decodeHtmlEntities = decodeHtmlEntities;
exports.cleanText = cleanText;
exports.extractMeta = extractMeta;
exports.extractTitle = extractTitle;
exports.extractJsonLdRecords = extractJsonLdRecords;
exports.extractCompanyName = extractCompanyName;
exports.extractPublishedAt = extractPublishedAt;
exports.extractExcerpt = extractExcerpt;
exports.extractMainText = extractMainText;
exports.extractLinks = extractLinks;
exports.selectCompanyLinks = selectCompanyLinks;
exports.findFeedUrls = findFeedUrls;
exports.findOfficialGithubOwner = findOfficialGithubOwner;
const domain_ts_1 = require("./domain.ts");
const ENTITY_MAP = {
    amp: "&",
    lt: "<",
    gt: ">",
    quot: '"',
    apos: "'",
    nbsp: " ",
};
function decodeHtmlEntities(value) {
    return value
        .replace(/&#(\d+);/g, (_, code) => String.fromCodePoint(Number(code)))
        .replace(/&#x([0-9a-f]+);/gi, (_, code) => String.fromCodePoint(Number.parseInt(code, 16)))
        .replace(/&([a-z]+);/gi, (whole, name) => ENTITY_MAP[name.toLowerCase()] ?? whole);
}
function cleanText(value) {
    return decodeHtmlEntities(value)
        .replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, " ")
        .replace(/<style\b[^>]*>[\s\S]*?<\/style>/gi, " ")
        .replace(/<noscript\b[^>]*>[\s\S]*?<\/noscript>/gi, " ")
        .replace(/<svg\b[^>]*>[\s\S]*?<\/svg>/gi, " ")
        .replace(/<[^>]+>/g, " ")
        .replace(/\s+/g, " ")
        .trim();
}
function getAttribute(tag, name) {
    const pattern = new RegExp(`${name}\\s*=\\s*(["'])(.*?)\\1`, "i");
    const match = tag.match(pattern);
    return match ? decodeHtmlEntities(match[2].trim()) : null;
}
function extractMeta(html, key) {
    const tags = html.match(/<meta\b[^>]*>/gi) ?? [];
    for (const tag of tags) {
        const name = getAttribute(tag, "name") ?? getAttribute(tag, "property") ?? getAttribute(tag, "itemprop");
        if (name?.toLowerCase() === key.toLowerCase()) {
            return getAttribute(tag, "content");
        }
    }
    return null;
}
function extractTitle(html) {
    const ogTitle = extractMeta(html, "og:title");
    if (ogTitle)
        return cleanText(ogTitle).slice(0, 240);
    const match = html.match(/<title\b[^>]*>([\s\S]*?)<\/title>/i);
    return match ? cleanText(match[1]).slice(0, 240) : "Untitled page";
}
function collectJsonLdRecords(value, output = []) {
    if (Array.isArray(value)) {
        value.forEach((item) => collectJsonLdRecords(item, output));
        return output;
    }
    if (!value || typeof value !== "object")
        return output;
    const record = value;
    output.push(record);
    if (Array.isArray(record["@graph"]))
        collectJsonLdRecords(record["@graph"], output);
    return output;
}
function extractJsonLdRecords(html) {
    const blocks = html.match(/<script\b[^>]*type=["']application\/ld\+json["'][^>]*>([\s\S]*?)<\/script>/gi) ?? [];
    const output = [];
    for (const block of blocks) {
        const body = block.replace(/^.*?>/s, "").replace(/<\/script>$/i, "").trim();
        try {
            collectJsonLdRecords(JSON.parse(body), output);
        }
        catch {
        }
    }
    return output;
}
function extractCompanyName(html, domain) {
    const siteName = extractMeta(html, "og:site_name");
    if (siteName && siteName.length >= 2 && siteName.length <= 100) {
        return { name: cleanText(siteName), confidence: 0.94 };
    }
    for (const record of extractJsonLdRecords(html)) {
        const type = String(record["@type"] ?? "").toLowerCase();
        const name = typeof record.name === "string" ? cleanText(record.name) : null;
        if ((type.includes("organization") || type.includes("corporation")) && name) {
            return { name, confidence: 0.9 };
        }
    }
    const title = extractTitle(html);
    const candidate = title.split(/\s+[|—–-]\s+/)[0]?.trim();
    if (candidate && candidate.length >= 2 && candidate.length <= 80) {
        return { name: candidate, confidence: 0.68 };
    }
    const label = domain.split(".")[0];
    return { name: label ? label[0].toUpperCase() + label.slice(1) : null, confidence: 0.45 };
}
function extractPublishedAt(html) {
    const candidates = [
        extractMeta(html, "article:published_time"),
        extractMeta(html, "datePublished"),
        extractMeta(html, "date"),
        extractMeta(html, "publish-date"),
        extractMeta(html, "parsely-pub-date"),
        ...extractJsonLdRecords(html).flatMap((record) => {
            const value = record.datePublished ?? record.dateCreated ?? record.uploadDate;
            return typeof value === "string" ? [value] : [];
        }),
    ].filter((value) => Boolean(value));
    const timeTags = html.match(/<time\b[^>]*>/gi) ?? [];
    for (const tag of timeTags) {
        const datetime = getAttribute(tag, "datetime");
        if (datetime)
            candidates.push(datetime);
    }
    for (const raw of candidates) {
        const date = new Date(raw);
        if (!Number.isNaN(date.getTime()))
            return date.toISOString();
    }
    return null;
}
function extractExcerpt(html, maxLength = 420) {
    const description = extractMeta(html, "description") ?? extractMeta(html, "og:description");
    if (description)
        return cleanText(description).slice(0, maxLength);
    const article = html.match(/<article\b[^>]*>([\s\S]*?)<\/article>/i)?.[1] ?? html;
    return cleanText(article).slice(0, maxLength);
}
function extractMainText(html, maxLength = 18_000) {
    const article = html.match(/<article\b[^>]*>([\s\S]*?)<\/article>/i)?.[1]
        ?? html.match(/<main\b[^>]*>([\s\S]*?)<\/main>/i)?.[1]
        ?? html;
    return cleanText(article).slice(0, maxLength);
}
function extractLinks(html, baseUrl) {
    const tags = html.match(/<(?:a|link)\b[^>]*>(?:[\s\S]*?<\/a>)?/gi) ?? [];
    const seen = new Set();
    const output = [];
    for (const tag of tags) {
        const href = getAttribute(tag, "href");
        if (!href || href.startsWith("mailto:") || href.startsWith("javascript:"))
            continue;
        try {
            const url = (0, domain_ts_1.canonicalizeHttpUrl)(href, baseUrl);
            const canonical = url.toString();
            if (seen.has(canonical))
                continue;
            seen.add(canonical);
            output.push({
                url: canonical,
                text: cleanText(tag.replace(/^<[^>]+>/, "").replace(/<\/a>$/i, "")).slice(0, 180),
                rel: getAttribute(tag, "rel") ?? "",
                type: getAttribute(tag, "type") ?? "",
            });
        }
        catch {
        }
    }
    return output;
}
function selectCompanyLinks(links, companyDomain, limit = 10) {
    const keyword = /\b(news|press|media|blog|release|launch|product|partner|customer|career|jobs|hiring|security|compliance|about)\b/i;
    return links
        .filter((link) => {
        const parsed = new URL(link.url);
        return (0, domain_ts_1.isSameCompanyDomain)(parsed.hostname, companyDomain) && keyword.test(`${parsed.pathname} ${link.text}`);
    })
        .sort((a, b) => Number(/news|press|release/i.test(b.url)) - Number(/news|press|release/i.test(a.url)))
        .slice(0, limit)
        .map((link) => link.url);
}
function findFeedUrls(links, companyDomain) {
    return links
        .filter((link) => {
        const parsed = new URL(link.url);
        return ((0, domain_ts_1.isSameCompanyDomain)(parsed.hostname, companyDomain) &&
            (/rss|atom|feed/i.test(link.type) || /rss|atom|feed/i.test(`${link.rel} ${parsed.pathname}`)));
    })
        .slice(0, 2)
        .map((link) => link.url);
}
function findOfficialGithubOwner(links) {
    for (const link of links) {
        const parsed = new URL(link.url);
        if (parsed.hostname !== "github.com" && parsed.hostname !== "www.github.com")
            continue;
        const parts = parsed.pathname.split("/").filter(Boolean);
        if (parts.length >= 1 && !["features", "topics", "marketplace", "orgs"].includes(parts[0].toLowerCase())) {
            return parts[0];
        }
    }
    return null;
}

};

__modules["/xml.ts"] = function(module, exports, require) {
"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.parseSitemap = parseSitemap;
exports.parseFeed = parseFeed;
exports.parseRobotsSitemaps = parseRobotsSitemaps;
const html_ts_1 = require("./html.ts");
function tagValue(block, tag) {
    const match = block.match(new RegExp(`<${tag}\\b[^>]*>([\\s\\S]*?)<\\/${tag}>`, "i"));
    return match ? (0, html_ts_1.cleanText)(match[1]) : null;
}
function parseSitemap(xml) {
    const entries = [];
    const blocks = xml.match(/<(?:url|sitemap)\b[^>]*>[\s\S]*?<\/(?:url|sitemap)>/gi) ?? [];
    for (const block of blocks) {
        const url = tagValue(block, "loc");
        if (!url)
            continue;
        const rawDate = tagValue(block, "lastmod");
        let lastmod = null;
        if (rawDate) {
            const parsed = new Date(rawDate);
            if (!Number.isNaN(parsed.getTime()))
                lastmod = parsed.toISOString();
        }
        entries.push({ url: (0, html_ts_1.decodeHtmlEntities)(url), lastmod });
    }
    return entries;
}
function parseFeed(xml) {
    const blocks = xml.match(/<(?:item|entry)\b[^>]*>[\s\S]*?<\/(?:item|entry)>/gi) ?? [];
    const entries = [];
    for (const block of blocks.slice(0, 30)) {
        const title = tagValue(block, "title") ?? "Untitled update";
        const rssLink = tagValue(block, "link");
        const atomLinkTag = block.match(/<link\b[^>]*href=["']([^"']+)["'][^>]*>/i)?.[1] ?? null;
        const url = rssLink ?? atomLinkTag;
        if (!url)
            continue;
        const rawDate = tagValue(block, "pubDate") ?? tagValue(block, "published") ?? tagValue(block, "updated");
        const parsedDate = rawDate ? new Date(rawDate) : null;
        const publishedAt = parsedDate && !Number.isNaN(parsedDate.getTime()) ? parsedDate.toISOString() : null;
        const excerpt = tagValue(block, "description") ?? tagValue(block, "summary") ?? tagValue(block, "content") ?? title;
        entries.push({ title, url: (0, html_ts_1.decodeHtmlEntities)(url), publishedAt, excerpt: excerpt.slice(0, 420) });
    }
    return entries;
}
function parseRobotsSitemaps(text) {
    return text
        .split(/\r?\n/)
        .map((line) => line.match(/^\s*sitemap\s*:\s*(\S+)/i)?.[1] ?? null)
        .filter((value) => Boolean(value))
        .slice(0, 5);
}

};

__modules["/request.ts"] = function(module, exports, require) {
"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.triggerPackRequestSchema = void 0;
const npm_zod_3_24_2_1 = require("npm:zod@3.24.2");
exports.triggerPackRequestSchema = npm_zod_3_24_2_1.z.object({
    company_domain: npm_zod_3_24_2_1.z.string().trim().min(3).max(253),
    goal: npm_zod_3_24_2_1.z.string().trim().min(3).max(500),
    lookback_days: npm_zod_3_24_2_1.z.coerce.number().int().min(1).max(90).default(90),
}).strict();

};

__modules["/events.ts"] = function(module, exports, require) {
"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.splitSentences = splitSentences;
exports.extractCandidateTriggers = extractCandidateTriggers;
exports.deduplicateCandidates = deduplicateCandidates;
const node_crypto_1 = require("node:crypto");
const RULES = [
    { type: "funding", pattern: /\b(raised|raises|funding round|series [a-f]|seed round|financing|strategic investment|secured funding)\b/i, strength: 0.9 },
    { type: "acquisition", pattern: /\b(acquired|acquires|acquisition|merger|merged with|to acquire)\b/i, strength: 0.94 },
    { type: "executive_change", pattern: /\b(appointed|named|joins as|hired as|new chief|new ceo|new cfo|new cto|steps down|resigns|leadership team)\b/i, strength: 0.76 },
    { type: "product_launch", pattern: /\b(launched|launches|introduces|introduced|unveiled|released|general availability|now available|announces new|new product|new platform|new feature)\b/i, strength: 0.78 },
    { type: "partnership", pattern: /\b(partnered with|partners with|partnership|strategic alliance|integration with|integrates with|distribution agreement|collaboration with)\b/i, strength: 0.72 },
    { type: "geographic_expansion", pattern: /\b(expands into|expanded into|new market|new region|new country|new office|opens? (?:an? )?(?:office|hub|location)|regional expansion|international expansion)\b/i, strength: 0.76 },
    { type: "pricing_change", pattern: /\b(new pricing|pricing update|price increase|price decrease|changed pricing|updated plans|new plan|subscription price)\b/i, strength: 0.64 },
    { type: "compliance", pattern: /\b(certified|certification|regulatory approval|approved by|soc 2|iso 27001|hipaa|pci dss|compliance program|security certification)\b/i, strength: 0.72 },
    { type: "technology_change", pattern: /\b(migrated to|migration to|adopted|open[- ]sourced|new api|developer platform|infrastructure|kubernetes|artificial intelligence|machine learning|security architecture|technical release)\b/i, strength: 0.62 },
    { type: "hiring", pattern: /\b(we are hiring|now hiring|join our team|open roles|job openings|hiring for|careers at|vacancies|recruiting)\b/i, strength: 0.56 },
];
const BOILERPLATE = /\b(cookie|privacy policy|terms of use|all rights reserved|subscribe to our newsletter|accept all|skip to content)\b/i;
function splitSentences(text) {
    return text
        .replace(/\s+/g, " ")
        .split(/(?<=[.!?])\s+|\s*[|•]\s*/)
        .map((sentence) => sentence.trim())
        .filter((sentence) => sentence.length >= 28 && sentence.length <= 420 && !BOILERPLATE.test(sentence));
}
function stableId(prefix, value) {
    return `${prefix}_${(0, node_crypto_1.createHash)("sha256").update(value).digest("hex").slice(0, 12)}`;
}
function normalizeEventText(text) {
    return text
        .replace(/\s+/g, " ")
        .replace(/^[\s:;,-]+|[\s:;,-]+$/g, "")
        .slice(0, 360);
}
function extractCandidateTriggers(evidence) {
    const candidates = [];
    for (const item of evidence) {
        const joined = [item.title, item.excerpt, item.content ?? ""].filter(Boolean).join(". ");
        const sentences = splitSentences(joined);
        for (const sentence of sentences) {
            for (const rule of RULES) {
                if (!rule.pattern.test(sentence))
                    continue;
                candidates.push({
                    type: rule.type,
                    event: normalizeEventText(sentence),
                    published_at: item.published_at,
                    evidence_ids: [item.id],
                    evidence_quality: item.source_quality,
                    event_strength: rule.strength,
                    source_text: sentence,
                });
                break;
            }
        }
        if (item.source_type === "jobs" && candidates.every((candidate) => !candidate.evidence_ids.includes(item.id))) {
            candidates.push({
                type: "hiring",
                event: normalizeEventText(item.excerpt || item.title),
                published_at: item.published_at,
                evidence_ids: [item.id],
                evidence_quality: item.source_quality,
                event_strength: 0.5,
                source_text: item.excerpt || item.title,
            });
        }
        if (item.source_type === "github" && candidates.every((candidate) => !candidate.evidence_ids.includes(item.id))) {
            candidates.push({
                type: "technology_change",
                event: normalizeEventText(item.excerpt || item.title),
                published_at: item.published_at,
                evidence_ids: [item.id],
                evidence_quality: item.source_quality,
                event_strength: 0.5,
                source_text: item.excerpt || item.title,
            });
        }
    }
    return deduplicateCandidates(candidates);
}
function tokens(value) {
    return new Set(value
        .toLowerCase()
        .replace(/[^a-z0-9\s]/g, " ")
        .split(/\s+/)
        .filter((token) => token.length >= 3 && !["the", "and", "for", "with", "from", "that", "this"].includes(token)));
}
function jaccard(a, b) {
    const intersection = [...a].filter((token) => b.has(token)).length;
    const union = new Set([...a, ...b]).size;
    return union === 0 ? 0 : intersection / union;
}
function deduplicateCandidates(candidates) {
    const sorted = [...candidates].sort((a, b) => {
        const aTime = a.published_at ? new Date(a.published_at).getTime() : 0;
        const bTime = b.published_at ? new Date(b.published_at).getTime() : 0;
        return bTime - aTime || b.evidence_quality - a.evidence_quality;
    });
    const clusters = [];
    for (const candidate of sorted) {
        const candidateTokens = tokens(candidate.event);
        const existing = clusters.find((cluster) => {
            if (cluster.type !== candidate.type)
                return false;
            const similarity = jaccard(tokens(cluster.event), candidateTokens);
            if (similarity >= 0.62)
                return true;
            if (cluster.published_at && candidate.published_at) {
                const days = Math.abs(new Date(cluster.published_at).getTime() - new Date(candidate.published_at).getTime()) / 86_400_000;
                return days <= 2 && similarity >= 0.45;
            }
            return false;
        });
        if (!existing) {
            clusters.push({ ...candidate, evidence_ids: [...candidate.evidence_ids] });
            continue;
        }
        existing.evidence_ids = [...new Set([...existing.evidence_ids, ...candidate.evidence_ids])];
        existing.evidence_quality = Math.max(existing.evidence_quality, candidate.evidence_quality);
        existing.event_strength = Math.max(existing.event_strength, candidate.event_strength);
        if (!existing.published_at && candidate.published_at)
            existing.published_at = candidate.published_at;
        if (candidate.event.length > existing.event.length && candidate.evidence_quality >= existing.evidence_quality) {
            existing.event = candidate.event;
            existing.source_text = candidate.source_text;
        }
    }
    return clusters.slice(0, 20).map((candidate) => ({
        ...candidate,
        event: candidate.event || stableId("event", candidate.source_text),
    }));
}

};

__modules["/scoring.ts"] = function(module, exports, require) {
"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.computeGoalRelevance = computeGoalRelevance;
exports.computeRecency = computeRecency;
exports.rankCandidates = rankCandidates;
exports.buildAction = buildAction;
const node_crypto_1 = require("node:crypto");
const STOPWORDS = new Set([
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in", "is", "it", "of", "on", "or", "that", "the", "their", "this", "to", "with", "them", "company", "sell",
]);
const TYPE_INTENTS = {
    funding: ["growth", "budget", "sales", "expansion", "software", "vendor", "investment", "procurement"],
    hiring: ["hiring", "recruiting", "talent", "workforce", "hr", "support", "operations", "headcount", "automation"],
    executive_change: ["leadership", "executive", "transformation", "strategy", "budget", "procurement", "change"],
    product_launch: ["product", "launch", "marketing", "sales", "support", "analytics", "growth", "integration"],
    partnership: ["partner", "integration", "platform", "distribution", "ecosystem", "channel", "alliance"],
    acquisition: ["integration", "migration", "consolidation", "security", "data", "operations", "transformation"],
    geographic_expansion: ["international", "localization", "payments", "compliance", "support", "operations", "expansion"],
    pricing_change: ["pricing", "billing", "revenue", "retention", "subscription", "monetization"],
    compliance: ["security", "compliance", "risk", "fraud", "audit", "identity", "regulatory"],
    technology_change: ["developer", "infrastructure", "observability", "cloud", "api", "data", "security", "ai", "automation", "platform"],
    other: ["change", "growth", "operations"],
};
const WHY = {
    funding: "Fresh financing can increase near-term capacity to buy tools, hire, and accelerate execution.",
    hiring: "Active hiring can reveal a growing workload, capability gap, or cost center that software may address.",
    executive_change: "A leadership change can reopen priorities, budgets, vendors, and transformation programs.",
    product_launch: "A launch can create immediate demands across growth, reliability, support, data, and operations.",
    partnership: "A new partnership or integration can create implementation work and adjacent commercial requirements.",
    acquisition: "An acquisition commonly creates integration, migration, governance, and consolidation work.",
    geographic_expansion: "Expansion can create localization, compliance, payments, staffing, and service-delivery needs.",
    pricing_change: "A pricing change can signal active monetization, retention, billing, or packaging work.",
    compliance: "A compliance or security milestone can expose active risk, audit, identity, and control requirements.",
    technology_change: "A technical change can create a timely need for infrastructure, developer, data, security, or automation tooling.",
    other: "The observed change may create a time-sensitive operational or commercial need.",
};
function tokenize(value) {
    return value
        .toLowerCase()
        .replace(/[^a-z0-9\s]/g, " ")
        .split(/\s+/)
        .filter((token) => token.length >= 2 && !STOPWORDS.has(token));
}
function computeGoalRelevance(type, event, goal) {
    const goalTokens = tokenize(goal);
    const eventTokens = new Set(tokenize(event));
    const intentTokens = new Set(TYPE_INTENTS[type]);
    const directMatches = goalTokens.filter((token) => eventTokens.has(token)).length;
    const intentMatches = goalTokens.filter((token) => intentTokens.has(token)).length;
    const direct = Math.min(1, directMatches / Math.max(2, Math.sqrt(goalTokens.length || 1)));
    const intent = Math.min(1, intentMatches / Math.max(1, Math.sqrt(goalTokens.length || 1)));
    const phraseBoosts = [
        [/recruit|talent|hiring|hr/i, "hiring", 0.45],
        [/support|contact center|customer service|call center/i, "hiring", 0.22],
        [/support|customer experience|customer service/i, "product_launch", 0.18],
        [/observability|developer|infrastructure|cloud|api|devops|platform/i, "technology_change", 0.45],
        [/security|fraud|risk|compliance|identity|audit/i, "compliance", 0.42],
        [/billing|pricing|subscription|revenue|monetization/i, "pricing_change", 0.42],
        [/international|localization|cross.border|global|payments/i, "geographic_expansion", 0.4],
        [/integration|migration|consolidation/i, "acquisition", 0.35],
    ];
    const phraseBoost = phraseBoosts
        .filter(([pattern, matchingType]) => matchingType === type && pattern.test(goal))
        .reduce((sum, [, , boost]) => sum + boost, 0);
    return clamp(0.12 + direct * 0.45 + intent * 0.43 + phraseBoost, 0, 1);
}
function computeRecency(publishedAt, observedAt, lookbackDays) {
    if (!publishedAt)
        return 0.22;
    const timestamp = new Date(publishedAt).getTime();
    if (Number.isNaN(timestamp))
        return 0.18;
    const ageDays = Math.max(0, (observedAt.getTime() - timestamp) / 86_400_000);
    const halfLife = Math.max(7, lookbackDays / 3);
    return clamp(Math.exp((-Math.log(2) * ageDays) / halfLife), 0.05, 1);
}
function clamp(value, min, max) {
    return Math.min(max, Math.max(min, value));
}
function idFor(candidate) {
    return `trg_${(0, node_crypto_1.createHash)("sha256").update(`${candidate.type}:${candidate.event}`).digest("hex").slice(0, 12)}`;
}
function rankCandidates(candidates, goal, lookbackDays, observedAt = new Date()) {
    return candidates
        .map((candidate) => {
        const relevance = computeGoalRelevance(candidate.type, candidate.event, goal);
        const recency = computeRecency(candidate.published_at, observedAt, lookbackDays);
        const evidenceQuality = clamp(candidate.evidence_quality + Math.min(0.14, (candidate.evidence_ids.length - 1) * 0.05), 0, 1);
        const score = 0.35 * relevance +
            0.25 * recency +
            0.25 * evidenceQuality +
            0.15 * candidate.event_strength;
        const confidence = clamp(0.55 * evidenceQuality + 0.25 * recency + 0.2 * candidate.event_strength, 0, 1);
        return {
            id: idFor(candidate),
            type: candidate.type,
            event: candidate.event,
            published_at: candidate.published_at,
            why_it_matters: `${WHY[candidate.type]} Relevance is assessed specifically against: “${goal.slice(0, 180)}”.`,
            relevance_to_goal: round(relevance),
            confidence: round(confidence),
            evidence_ids: candidate.evidence_ids,
            score: Math.round(score * 100),
        };
    })
        .filter((candidate) => candidate.score >= 28)
        .sort((a, b) => b.score - a.score || b.confidence - a.confidence)
        .slice(0, 6);
}
function buildAction(ranked, goal) {
    const best = ranked[0];
    if (!best) {
        return {
            score: 0,
            recommendation: "skip",
            reason: "Insufficient defensible recent evidence was found for this company and objective.",
            angle: null,
        };
    }
    if (best.score >= 64 && best.confidence >= 0.55) {
        return {
            score: best.score,
            recommendation: "act_now",
            reason: `A recent ${best.type.replaceAll("_", " ")} signal is both evidence-backed and relevant to the supplied objective.`,
            angle: `Connect the observed event directly to the operational outcome in “${goal.slice(0, 180)}”; cite evidence ${best.evidence_ids.join(", ")}.`,
        };
    }
    if (best.score >= 42) {
        return {
            score: best.score,
            recommendation: "monitor",
            reason: "A plausible signal exists, but recency, evidence strength, or goal relevance is not yet strong enough for immediate action.",
            angle: `Monitor the cited event and use it only as a cautious, evidence-linked opening for “${goal.slice(0, 180)}”.`,
        };
    }
    return {
        score: best.score,
        recommendation: "skip",
        reason: "The available evidence does not clear the actionability threshold for this objective.",
        angle: null,
    };
}
function round(value) {
    return Math.round(value * 1000) / 1000;
}

};

__modules["/sources/first-party.ts"] = function(module, exports, require) {
"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.collectFirstPartyEvidence = collectFirstPartyEvidence;
const node_crypto_1 = require("node:crypto");
const domain_ts_1 = require("../domain.ts");
const html_ts_1 = require("../html.ts");
const http_ts_1 = require("../http.ts");
const xml_ts_1 = require("../xml.ts");
function evidenceId(url, title) {
    return `ev_${(0, node_crypto_1.createHash)("sha256").update(`${url}:${title}`).digest("hex").slice(0, 12)}`;
}
function isWithinLookback(date, lookbackDays) {
    if (!date)
        return true;
    const age = (Date.now() - new Date(date).getTime()) / 86_400_000;
    return age >= -2 && age <= lookbackDays + 3;
}
function inferSourceType(url, title) {
    const value = `${new URL(url).pathname} ${title}`;
    return /career|jobs|vacanc|hiring|join-us|positions/i.test(value) ? "jobs" : "company";
}
function pageToEvidence(url, html, lookbackDays) {
    const title = (0, html_ts_1.extractTitle)(html);
    const publishedAt = (0, html_ts_1.extractPublishedAt)(html);
    const sourceType = inferSourceType(url, title);
    if (!isWithinLookback(publishedAt, lookbackDays))
        return null;
    const excerpt = (0, html_ts_1.extractExcerpt)(html);
    const content = (0, html_ts_1.extractMainText)(html);
    if (!excerpt && !content)
        return null;
    if (!publishedAt &&
        sourceType === "company" &&
        !/news|press|blog|release|launch|partner|product|security|compliance/i.test(new URL(url).pathname)) {
        return null;
    }
    return {
        id: evidenceId(url, title),
        source_type: sourceType,
        source_url: url,
        title,
        published_at: publishedAt,
        excerpt: excerpt || content.slice(0, 420),
        source_quality: publishedAt ? 0.91 : sourceType === "jobs" ? 0.78 : 0.7,
        content,
    };
}
function sameCompanyUrl(raw, domain) {
    try {
        return (0, domain_ts_1.isSameCompanyDomain)(new URL(raw).hostname, domain);
    }
    catch {
        return false;
    }
}
function isAtsLink(link) {
    const host = new URL(link.url).hostname.toLowerCase();
    return [
        "boards.greenhouse.io",
        "job-boards.greenhouse.io",
        "jobs.lever.co",
        "jobs.eu.lever.co",
        "jobs.ashbyhq.com",
    ].includes(host);
}
async function collectFirstPartyEvidence(inputDomain, lookbackDays) {
    const domain = (0, domain_ts_1.normalizeCompanyDomain)(inputDomain);
    const errors = [];
    let sourcesChecked = 0;
    const homeCandidates = [`https://${domain}/`, `https://www.${domain}/`];
    sourcesChecked += homeCandidates.length;
    const homeAttempts = await Promise.all(homeCandidates.map(async (candidate) => {
        try {
            const response = await (0, http_ts_1.fetchTextSafe)(candidate);
            if (response.status >= 200 && response.status < 400 && /html/i.test(response.contentType || "text/html")) {
                return response;
            }
            errors.push(`home:${new URL(candidate).hostname}:${response.status}`);
        }
        catch (error) {
            errors.push(`home:${new URL(candidate).hostname}:${error instanceof Error ? error.message : "failed"}`);
        }
        return null;
    }));
    const home = homeAttempts.find(Boolean);
    if (!home) {
        return {
            companyName: null,
            companyNameConfidence: 0,
            evidence: [],
            officialGithubOwner: null,
            officialAtsUrls: [],
            sourcesChecked,
            errors,
        };
    }
    const homeUrl = home.url;
    const homeHtml = home.text;
    const identity = (0, html_ts_1.extractCompanyName)(homeHtml, domain);
    const homeLinks = (0, html_ts_1.extractLinks)(homeHtml, homeUrl);
    const officialGithubOwner = (0, html_ts_1.findOfficialGithubOwner)(homeLinks);
    const auxiliaryUrls = [`https://${domain}/robots.txt`, `https://${domain}/sitemap.xml`];
    sourcesChecked += auxiliaryUrls.length;
    const auxiliary = await (0, http_ts_1.mapWithConcurrency)(auxiliaryUrls, 2, async (url) => {
        try {
            const response = await (0, http_ts_1.fetchTextSafe)(url);
            return response.status >= 200 && response.status < 400 ? response : null;
        }
        catch (error) {
            errors.push(`aux:${new URL(url).pathname}:${error instanceof Error ? error.message : "failed"}`);
            return null;
        }
    });
    const robots = auxiliary[0];
    const defaultSitemap = auxiliary[1];
    const declaredSitemaps = robots
        ? (0, xml_ts_1.parseRobotsSitemaps)(robots.text).filter((url) => sameCompanyUrl(url, domain))
        : [];
    const sitemapUrls = [...new Set([
            ...(defaultSitemap ? [defaultSitemap.url] : []),
            ...declaredSitemaps,
        ])].slice(0, 3);
    const sitemapDocuments = new Map();
    if (defaultSitemap)
        sitemapDocuments.set(defaultSitemap.url, defaultSitemap.text);
    const missingSitemaps = sitemapUrls.filter((url) => !sitemapDocuments.has(url));
    sourcesChecked += missingSitemaps.length;
    const missingResponses = await (0, http_ts_1.mapWithConcurrency)(missingSitemaps, 2, async (url) => {
        try {
            const response = await (0, http_ts_1.fetchTextSafe)(url, { policy: { maxBytes: 2_000_000 } });
            return response.status >= 200 && response.status < 400 ? response : null;
        }
        catch (error) {
            errors.push(`sitemap:${error instanceof Error ? error.message : "failed"}`);
            return null;
        }
    });
    missingResponses.filter(Boolean).forEach((response) => sitemapDocuments.set(response.url, response.text));
    const initialEntries = [...sitemapDocuments.values()].flatMap(xml_ts_1.parseSitemap);
    const nestedSitemaps = initialEntries
        .map((entry) => entry.url)
        .filter((url) => /\.xml(?:$|\?)/i.test(url) && sameCompanyUrl(url, domain))
        .slice(0, 2);
    sourcesChecked += nestedSitemaps.length;
    const nestedResponses = await (0, http_ts_1.mapWithConcurrency)(nestedSitemaps, 2, async (url) => {
        try {
            const response = await (0, http_ts_1.fetchTextSafe)(url, { policy: { maxBytes: 2_000_000 } });
            return response.status >= 200 && response.status < 400 ? response.text : "";
        }
        catch (error) {
            errors.push(`nested-sitemap:${error instanceof Error ? error.message : "failed"}`);
            return "";
        }
    });
    const sitemapEntries = [...initialEntries, ...nestedResponses.flatMap(xml_ts_1.parseSitemap)];
    const relevantPattern = /news|press|media|blog|release|launch|product|partner|customer|career|jobs|security|compliance/i;
    const fromSitemap = sitemapEntries
        .filter((entry) => {
        try {
            const parsed = new URL(entry.url);
            return ((0, domain_ts_1.isSameCompanyDomain)(parsed.hostname, domain) &&
                relevantPattern.test(parsed.pathname) &&
                isWithinLookback(entry.lastmod, lookbackDays));
        }
        catch {
            return false;
        }
    })
        .sort((a, b) => (b.lastmod ?? "").localeCompare(a.lastmod ?? ""))
        .slice(0, 10)
        .map((entry) => entry.url);
    const selectedPages = [...new Set([...(0, html_ts_1.selectCompanyLinks)(homeLinks, domain, 8), ...fromSitemap])].slice(0, 10);
    const feedUrls = (0, html_ts_1.findFeedUrls)(homeLinks, domain);
    sourcesChecked += selectedPages.length + feedUrls.length;
    const [pageResults, feedResults] = await Promise.all([
        (0, http_ts_1.mapWithConcurrency)(selectedPages, 4, async (url) => {
            try {
                const response = await (0, http_ts_1.fetchTextSafe)(url);
                if (response.status < 200 || response.status >= 400 || !/html|text/i.test(response.contentType || "text/html")) {
                    return { evidence: null, links: [] };
                }
                return {
                    evidence: pageToEvidence(response.url, response.text, lookbackDays),
                    links: (0, html_ts_1.extractLinks)(response.text, response.url),
                };
            }
            catch (error) {
                errors.push(`page:${new URL(url).pathname}:${error instanceof Error ? error.message : "failed"}`);
                return { evidence: null, links: [] };
            }
        }),
        (0, http_ts_1.mapWithConcurrency)(feedUrls, 2, async (url) => {
            try {
                const response = await (0, http_ts_1.fetchTextSafe)(url);
                if (response.status < 200 || response.status >= 400)
                    return [];
                return (0, xml_ts_1.parseFeed)(response.text)
                    .filter((entry) => isWithinLookback(entry.publishedAt, lookbackDays))
                    .filter((entry) => sameCompanyUrl(entry.url, domain))
                    .slice(0, 10)
                    .map((entry) => ({
                    id: evidenceId(entry.url, entry.title),
                    source_type: inferSourceType(entry.url, entry.title),
                    source_url: entry.url,
                    title: entry.title,
                    published_at: entry.publishedAt,
                    excerpt: entry.excerpt,
                    source_quality: entry.publishedAt ? 0.9 : 0.74,
                    content: entry.excerpt,
                }));
            }
            catch (error) {
                errors.push(`feed:${error instanceof Error ? error.message : "failed"}`);
                return [];
            }
        }),
    ]);
    const pageEvidence = pageResults
        .map((result) => result.evidence)
        .filter((item) => Boolean(item));
    const allDiscoveredLinks = [...homeLinks, ...pageResults.flatMap((result) => result.links)];
    const officialAtsUrls = [...new Set(allDiscoveredLinks.filter(isAtsLink).map((link) => link.url))].slice(0, 3);
    const evidence = [...pageEvidence, ...feedResults.flat()];
    const deduped = [...new Map(evidence.map((item) => [item.source_url, item])).values()].slice(0, 20);
    return {
        companyName: identity.name,
        companyNameConfidence: identity.confidence,
        evidence: deduped,
        officialGithubOwner,
        officialAtsUrls,
        sourcesChecked,
        errors,
    };
}

};

__modules["/sources/gdelt.ts"] = function(module, exports, require) {
"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.collectGdeltEvidence = collectGdeltEvidence;
const node_crypto_1 = require("node:crypto");
const html_ts_1 = require("../html.ts");
const http_ts_1 = require("../http.ts");
function parseGdeltDate(raw) {
    if (!raw)
        return null;
    const compact = raw.match(/^(\d{4})(\d{2})(\d{2})T?(\d{2})?(\d{2})?(\d{2})?Z?$/);
    if (compact) {
        const [, year, month, day, hour = "00", minute = "00", second = "00"] = compact;
        const date = new Date(`${year}-${month}-${day}T${hour}:${minute}:${second}Z`);
        return Number.isNaN(date.getTime()) ? null : date.toISOString();
    }
    const date = new Date(raw);
    return Number.isNaN(date.getTime()) ? null : date.toISOString();
}
function evidenceId(url, title) {
    return `ev_${(0, node_crypto_1.createHash)("sha256").update(`${url}:${title}`).digest("hex").slice(0, 12)}`;
}
function mentionsCompany(value, nameTokens, domainLabel) {
    const normalized = value.toLowerCase();
    if (normalized.includes(domainLabel))
        return true;
    const meaningful = nameTokens.filter((token) => token.length >= 4);
    if (meaningful.length === 0)
        return false;
    return meaningful.every((token) => normalized.includes(token)) || meaningful.some((token) => normalized.includes(token));
}
async function collectGdeltEvidence(companyName, domain, lookbackDays) {
    const errors = [];
    const fallbackName = domain.split(".")[0].replace(/[-_]/g, " ");
    const searchName = (companyName ?? fallbackName).replace(/["()]/g, " ").replace(/\s+/g, " ").trim();
    if (searchName.length < 2) {
        return {
            companyName,
            companyNameConfidence: 0,
            evidence: [],
            sourcesChecked: 0,
            errors: ["gdelt:company name unavailable"],
        };
    }
    const url = new URL("https://api.gdeltproject.org/api/v2/doc/doc");
    url.searchParams.set("query", `\"${searchName}\"`);
    url.searchParams.set("mode", "ArtList");
    url.searchParams.set("maxrecords", "20");
    url.searchParams.set("format", "json");
    url.searchParams.set("timespan", `${Math.min(90, lookbackDays)}d`);
    url.searchParams.set("sort", "HybridRel");
    try {
        const response = await (0, http_ts_1.fetchJsonSafe)(url.toString(), {
            policy: { timeoutMs: 4_500, maxBytes: 1_500_000 },
        });
        const nameTokens = searchName.toLowerCase().split(/\s+/).filter((token) => token.length >= 3);
        const domainLabel = domain.split(".")[0].toLowerCase();
        const articles = (response.data.articles ?? [])
            .filter((article) => article.url && article.title)
            .filter((article) => mentionsCompany(article.title ?? "", nameTokens, domainLabel))
            .slice(0, 8);
        const checked = await (0, http_ts_1.mapWithConcurrency)(articles, 3, async (article) => {
            const sourceUrl = article.url_mobile || article.url;
            const gdeltTitle = article.title.replace(/\s+/g, " ").trim().slice(0, 260);
            const gdeltDate = parseGdeltDate(article.seendate);
            try {
                const original = await (0, http_ts_1.fetchTextSafe)(sourceUrl, { policy: { timeoutMs: 3_500, maxBytes: 1_500_000 } });
                if (original.status >= 200 && original.status < 300 && /html|text/i.test(original.contentType || "text/html")) {
                    const title = (0, html_ts_1.extractTitle)(original.text) || gdeltTitle;
                    const excerpt = (0, html_ts_1.extractExcerpt)(original.text);
                    const content = (0, html_ts_1.extractMainText)(original.text, 6_000);
                    const factualText = `${title}. ${excerpt}. ${content}`;
                    if (mentionsCompany(factualText, nameTokens, domainLabel)) {
                        return {
                            id: evidenceId(original.url, title),
                            source_type: "news",
                            source_url: original.url,
                            title: title.slice(0, 260),
                            published_at: (0, html_ts_1.extractPublishedAt)(original.text) ?? gdeltDate,
                            excerpt: (excerpt || gdeltTitle).slice(0, 420),
                            source_quality: 0.72,
                            content,
                        };
                    }
                }
            }
            catch (error) {
                errors.push(`news:${error instanceof Error ? error.message : "failed"}`);
            }
            return {
                id: evidenceId(sourceUrl, gdeltTitle),
                source_type: "news",
                source_url: sourceUrl,
                title: gdeltTitle,
                published_at: gdeltDate,
                excerpt: gdeltTitle,
                source_quality: 0.56,
                content: gdeltTitle,
            };
        });
        return {
            companyName,
            companyNameConfidence: companyName ? 0.5 : 0,
            evidence: checked,
            sourcesChecked: 1 + articles.length,
            errors,
        };
    }
    catch (error) {
        errors.push(`gdelt:${error instanceof Error ? error.message : "failed"}`);
        return { companyName, companyNameConfidence: 0, evidence: [], sourcesChecked: 1, errors };
    }
}

};

__modules["/sources/ats.ts"] = function(module, exports, require) {
"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.discoverAtsBoards = discoverAtsBoards;
exports.collectAtsEvidence = collectAtsEvidence;
const node_crypto_1 = require("node:crypto");
const html_ts_1 = require("../html.ts");
const http_ts_1 = require("../http.ts");
function evidenceId(url, value) {
    return `ev_${(0, node_crypto_1.createHash)("sha256").update(`${url}:${value}`).digest("hex").slice(0, 12)}`;
}
function validSlug(value) {
    const slug = value.trim().replace(/^\/+|\/+$/g, "");
    return /^[a-z0-9][a-z0-9_-]{1,80}$/i.test(slug) ? slug : null;
}
function discoverAtsBoards(urls) {
    const boards = new Map();
    for (const raw of urls) {
        let url;
        try {
            url = new URL(raw);
        }
        catch {
            continue;
        }
        const host = url.hostname.toLowerCase();
        const parts = url.pathname.split("/").filter(Boolean);
        if (["boards.greenhouse.io", "job-boards.greenhouse.io"].includes(host)) {
            const querySlug = url.searchParams.get("for");
            const slug = validSlug(querySlug ?? parts[0] ?? "");
            if (slug) {
                const board = {
                    provider: "greenhouse",
                    slug,
                    apiUrl: `https://boards-api.greenhouse.io/v1/boards/${encodeURIComponent(slug)}/jobs?content=true`,
                    publicUrl: `https://job-boards.greenhouse.io/${encodeURIComponent(slug)}`,
                };
                boards.set(`${board.provider}:${slug}`, board);
            }
        }
        if (["jobs.lever.co", "jobs.eu.lever.co"].includes(host)) {
            const slug = validSlug(parts[0] ?? "");
            if (slug) {
                const eu = host.includes("eu.lever.co");
                const apiHost = eu ? "api.eu.lever.co" : "api.lever.co";
                const board = {
                    provider: "lever",
                    slug,
                    apiUrl: `https://${apiHost}/v0/postings/${encodeURIComponent(slug)}?mode=json`,
                    publicUrl: `https://${host}/${encodeURIComponent(slug)}`,
                };
                boards.set(`${board.provider}:${slug}`, board);
            }
        }
        if (host === "jobs.ashbyhq.com") {
            const slug = validSlug(parts[0] ?? "");
            if (slug) {
                const board = {
                    provider: "ashby",
                    slug,
                    apiUrl: `https://api.ashbyhq.com/posting-api/job-board/${encodeURIComponent(slug)}`,
                    publicUrl: `https://jobs.ashbyhq.com/${encodeURIComponent(slug)}`,
                };
                boards.set(`${board.provider}:${slug}`, board);
            }
        }
    }
    return [...boards.values()].slice(0, 2);
}
function summarizeRoles(roles) {
    const samples = roles.slice(0, 8).map((role) => {
        const context = [role.team, role.location].filter(Boolean).join(", ");
        return context ? `${role.title} (${context})` : role.title;
    });
    return samples.join("; ").slice(0, 720);
}
function latestDate(rawDates) {
    const values = rawDates
        .map((raw) => {
        if (raw === null || raw === undefined)
            return null;
        const date = new Date(raw);
        return Number.isNaN(date.getTime()) ? null : date;
    })
        .filter((value) => Boolean(value))
        .filter((date) => date.getTime() <= Date.now() + 2 * 86_400_000)
        .sort((a, b) => b.getTime() - a.getTime());
    return values[0]?.toISOString() ?? null;
}
async function collectBoard(board) {
    if (board.provider === "greenhouse") {
        const { data } = await (0, http_ts_1.fetchJsonSafe)(board.apiUrl, { policy: { maxBytes: 1_500_000 } });
        const jobs = (data.jobs ?? []).filter((job) => job.title).slice(0, 100);
        if (jobs.length === 0)
            return null;
        const roles = jobs.map((job) => ({
            title: (0, html_ts_1.cleanText)(job.title ?? "Untitled role"),
            location: (0, html_ts_1.cleanText)(job.location?.name ?? ""),
            team: (0, html_ts_1.cleanText)(job.departments?.map((department) => department.name).filter(Boolean).join(" / ") ?? ""),
        }));
        const title = `${jobs.length} current public roles on the company Greenhouse board`;
        return {
            id: evidenceId(board.publicUrl, title),
            source_type: "jobs",
            source_url: board.publicUrl,
            title,
            published_at: latestDate(jobs.map((job) => job.updated_at)),
            excerpt: `${title}. Sample roles: ${summarizeRoles(roles)}.`,
            source_quality: 0.88,
            content: `${title}. ${summarizeRoles(roles)}`,
        };
    }
    if (board.provider === "lever") {
        const { data } = await (0, http_ts_1.fetchJsonSafe)(board.apiUrl, { policy: { maxBytes: 1_500_000 } });
        const jobs = Array.isArray(data) ? data.filter((job) => job.text).slice(0, 100) : [];
        if (jobs.length === 0)
            return null;
        const roles = jobs.map((job) => ({
            title: (0, html_ts_1.cleanText)(job.text ?? "Untitled role"),
            location: (0, html_ts_1.cleanText)(job.categories?.location ?? ""),
            team: (0, html_ts_1.cleanText)(job.categories?.team ?? job.categories?.department ?? ""),
        }));
        const title = `${jobs.length} current public roles on the company Lever board`;
        return {
            id: evidenceId(board.publicUrl, title),
            source_type: "jobs",
            source_url: board.publicUrl,
            title,
            published_at: latestDate(jobs.map((job) => job.createdAt)),
            excerpt: `${title}. Sample roles: ${summarizeRoles(roles)}.`,
            source_quality: 0.88,
            content: `${title}. ${summarizeRoles(roles)}`,
        };
    }
    const { data } = await (0, http_ts_1.fetchJsonSafe)(board.apiUrl, { policy: { maxBytes: 1_500_000 } });
    const jobs = (data.jobs ?? []).filter((job) => job.title).slice(0, 100);
    if (jobs.length === 0)
        return null;
    const roles = jobs.map((job) => ({
        title: (0, html_ts_1.cleanText)(job.title ?? "Untitled role"),
        location: (0, html_ts_1.cleanText)(job.location ?? ""),
        team: (0, html_ts_1.cleanText)(job.team ?? job.department ?? ""),
    }));
    const title = `${jobs.length} current public roles on the company Ashby board`;
    return {
        id: evidenceId(board.publicUrl, title),
        source_type: "jobs",
        source_url: board.publicUrl,
        title,
        published_at: latestDate(jobs.map((job) => job.publishedAt)),
        excerpt: `${title}. Sample roles: ${summarizeRoles(roles)}.`,
        source_quality: 0.88,
        content: `${title}. ${summarizeRoles(roles)}`,
    };
}
async function collectAtsEvidence(urls) {
    const boards = discoverAtsBoards(urls);
    if (boards.length === 0) {
        return { companyName: null, companyNameConfidence: 0, evidence: [], sourcesChecked: 0, errors: [] };
    }
    const evidence = [];
    const errors = [];
    for (const board of boards) {
        try {
            const item = await collectBoard(board);
            if (item)
                evidence.push(item);
        }
        catch (error) {
            errors.push(`ats:${board.provider}:${error instanceof Error ? error.message : "failed"}`);
        }
    }
    return {
        companyName: null,
        companyNameConfidence: 0,
        evidence,
        sourcesChecked: boards.length,
        errors,
    };
}

};

__modules["/sources/github.ts"] = function(module, exports, require) {
"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.collectGithubEvidence = collectGithubEvidence;
const node_crypto_1 = require("node:crypto");
const http_ts_1 = require("../http.ts");
function evidenceId(url) {
    return `ev_${(0, node_crypto_1.createHash)("sha256").update(url).digest("hex").slice(0, 12)}`;
}
async function collectGithubEvidence(owner, lookbackDays) {
    if (!owner) {
        return { companyName: null, companyNameConfidence: 0, evidence: [], sourcesChecked: 0, errors: [] };
    }
    const errors = [];
    const endpoints = [
        `https://api.github.com/orgs/${encodeURIComponent(owner)}/repos?sort=pushed&per_page=15`,
        `https://api.github.com/users/${encodeURIComponent(owner)}/repos?sort=pushed&per_page=15`,
    ];
    for (const endpoint of endpoints) {
        try {
            const response = await (0, http_ts_1.fetchJsonSafe)(endpoint, {
                headers: { accept: "application/vnd.github+json" },
            });
            if (!Array.isArray(response.data))
                continue;
            const evidence = response.data
                .filter((repo) => repo.html_url && repo.full_name && repo.pushed_at && !repo.archived && !repo.fork)
                .filter((repo) => {
                const age = (Date.now() - new Date(repo.pushed_at).getTime()) / 86_400_000;
                return age >= -2 && age <= lookbackDays;
            })
                .slice(0, 6)
                .map((repo) => {
                const pushedAt = new Date(repo.pushed_at).toISOString();
                const excerpt = `${repo.full_name} was pushed on ${pushedAt.slice(0, 10)}${repo.description ? `; repository description: ${repo.description}` : ""}.`;
                return {
                    id: evidenceId(repo.html_url),
                    source_type: "github",
                    source_url: repo.html_url,
                    title: `Official GitHub activity: ${repo.full_name}`,
                    published_at: pushedAt,
                    excerpt: excerpt.slice(0, 420),
                    source_quality: 0.82,
                    content: excerpt,
                };
            });
            return { companyName: null, companyNameConfidence: 0, evidence, sourcesChecked: 1, errors };
        }
        catch (error) {
            errors.push(`github:${error instanceof Error ? error.message : "failed"}`);
        }
    }
    return { companyName: null, companyNameConfidence: 0, evidence: [], sourcesChecked: 2, errors };
}

};

__modules["/engine.ts"] = function(module, exports, require) {
"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.clearTriggerPackCache = clearTriggerPackCache;
exports.dedupeEvidence = dedupeEvidence;
exports.assembleTriggerPack = assembleTriggerPack;
exports.generateTriggerPack = generateTriggerPack;
const node_crypto_1 = require("node:crypto");
const cache_ts_1 = require("./cache.ts");
const domain_ts_1 = require("./domain.ts");
const events_ts_1 = require("./events.ts");
const scoring_ts_1 = require("./scoring.ts");
const ats_ts_1 = require("./sources/ats.ts");
const first_party_ts_1 = require("./sources/first-party.ts");
const gdelt_ts_1 = require("./sources/gdelt.ts");
const github_ts_1 = require("./sources/github.ts");
const resultCache = new cache_ts_1.TtlLru(64, 5 * 60_000);
function emptyCollection(error) {
    return {
        companyName: null,
        companyNameConfidence: 0,
        evidence: [],
        officialGithubOwner: null,
        officialAtsUrls: [],
        sourcesChecked: 0,
        errors: [error],
    };
}
async function withCollectionDeadline(promise, milliseconds, label) {
    let timer;
    try {
        return await Promise.race([
            promise,
            new Promise((resolve) => {
                timer = setTimeout(() => resolve(emptyCollection(`${label}:deadline_exceeded`)), milliseconds);
            }),
        ]);
    }
    finally {
        if (timer)
            clearTimeout(timer);
    }
}
function clearTriggerPackCache() {
    resultCache.clear();
}
function resultCacheKey(domain, goal, lookbackDays) {
    return `${domain}|${goal.trim().toLowerCase().replace(/\s+/g, " ")}|${lookbackDays}`;
}
function dedupeEvidence(items) {
    const byUrl = new Map();
    for (const item of items) {
        const existing = byUrl.get(item.source_url);
        if (!existing ||
            item.source_quality > existing.source_quality ||
            item.excerpt.length > existing.excerpt.length) {
            byUrl.set(item.source_url, item);
        }
    }
    return [...byUrl.values()]
        .sort((a, b) => {
        const aTime = a.published_at ? new Date(a.published_at).getTime() : 0;
        const bTime = b.published_at ? new Date(b.published_at).getTime() : 0;
        return bTime - aTime || b.source_quality - a.source_quality;
    })
        .slice(0, 30);
}
function cloneCachedResult(cached) {
    const cloned = structuredClone(cached);
    cloned.request_id = (0, node_crypto_1.randomUUID)();
    cloned.observed_at = new Date().toISOString();
    cloned.diagnostics.runtime_ms = 0;
    return cloned;
}
function assembleTriggerPack(input, domain, collections, observedAt = new Date(), runtimeMs = 0) {
    const { firstParty, gdelt, github, ats } = collections;
    const evidence = dedupeEvidence([
        ...firstParty.evidence,
        ...gdelt.evidence,
        ...github.evidence,
        ...ats.evidence,
    ]);
    const evidenceIds = new Set(evidence.map((item) => item.id));
    const candidates = (0, events_ts_1.extractCandidateTriggers)(evidence)
        .map((candidate) => ({
        ...candidate,
        evidence_ids: candidate.evidence_ids.filter((id) => evidenceIds.has(id)),
    }))
        .filter((candidate) => candidate.evidence_ids.length > 0);
    const ranked = (0, scoring_ts_1.rankCandidates)(candidates, input.goal, input.lookback_days, observedAt);
    const action = (0, scoring_ts_1.buildAction)(ranked, input.goal);
    return {
        request_id: (0, node_crypto_1.randomUUID)(),
        observed_at: observedAt.toISOString(),
        company: {
            name: firstParty.companyName,
            domain,
            confidence: firstParty.companyNameConfidence,
        },
        best_trigger: ranked[0] ?? null,
        other_triggers: ranked.slice(1),
        action,
        evidence,
        diagnostics: {
            sources_checked: firstParty.sourcesChecked + gdelt.sourcesChecked + github.sourcesChecked + ats.sourcesChecked,
            dated_sources_found: evidence.filter((item) => item.published_at).length,
            runtime_ms: runtimeMs,
            upstream_errors: [
                ...firstParty.errors,
                ...gdelt.errors,
                ...github.errors,
                ...ats.errors,
            ].slice(0, 12),
        },
    };
}
async function generateTriggerPack(input) {
    const started = performance.now();
    const observedAt = new Date();
    const domain = (0, domain_ts_1.normalizeCompanyDomain)(input.company_domain);
    const cacheKey = resultCacheKey(domain, input.goal, input.lookback_days);
    const cached = resultCache.get(cacheKey);
    if (cached)
        return cloneCachedResult(cached);
    const firstParty = await withCollectionDeadline((0, first_party_ts_1.collectFirstPartyEvidence)(domain, input.lookback_days), 9_000, "first_party");
    const [gdelt, github, ats] = await Promise.all([
        withCollectionDeadline((0, gdelt_ts_1.collectGdeltEvidence)(firstParty.companyName, domain, input.lookback_days), 5_000, "gdelt"),
        withCollectionDeadline((0, github_ts_1.collectGithubEvidence)(firstParty.officialGithubOwner, input.lookback_days), 5_000, "github"),
        withCollectionDeadline((0, ats_ts_1.collectAtsEvidence)(firstParty.officialAtsUrls ?? []), 5_000, "ats"),
    ]);
    const result = assembleTriggerPack(input, domain, { firstParty, gdelt, github, ats }, observedAt, Math.round(performance.now() - started));
    resultCache.set(cacheKey, structuredClone(result));
    return result;
}

};

__modules["/openapi.ts"] = function(module, exports, require) {
"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.buildOpenApi = buildOpenApi;
function buildOpenApi(baseUrl) {
    const triggerTypes = ["funding", "hiring", "executive_change", "product_launch", "partnership", "acquisition", "geographic_expansion", "pricing_change", "compliance", "technology_change", "other"];
    return {
        openapi: "3.1.0",
        info: {
            title: "TriggerPack API",
            version: "0.1.0",
            description: "Evidence-backed recent company triggers ranked against a specific objective.",
            "x-guidance": "Use POST /v1/company-trigger-pack when you know a company's public domain and need verified recent events that could justify action now. Supply company_domain, goal, and optional lookback_days. Facts are cited; inference is separated; a truthful negative result is valid.",
        },
        servers: [{ url: baseUrl }],
        paths: {
            "/health": {
                get: {
                    operationId: "health",
                    summary: "Service health",
                    responses: { "200": { description: "Operational status", content: { "application/json": { schema: { type: "object" } } } } },
                },
            },
            "/v1/company-trigger-pack": {
                post: {
                    operationId: "createCompanyTriggerPack",
                    summary: "Find a company's best recent action trigger",
                    description: "Searches first-party company pages, feeds, recent public news, officially linked job boards and GitHub activity. Returns ranked factual triggers, dated evidence, confidence and an action recommendation.",
                    "x-payment-info": { price: { mode: "fixed", currency: "USD", amount: "0.250000" }, protocols: [{ x402: {} }] },
                    requestBody: {
                        required: true,
                        content: {
                            "application/json": {
                                schema: { $ref: "#/components/schemas/TriggerPackRequest" },
                                example: { company_domain: "cloudflare.com", goal: "sell developer tooling", lookback_days: 90 },
                            },
                        },
                    },
                    responses: {
                        "200": { description: "Evidence-backed trigger pack", content: { "application/json": { schema: { $ref: "#/components/schemas/TriggerPackResponse" } } } },
                        "400": { description: "Invalid request after payment authorization", content: { "application/json": { schema: { $ref: "#/components/schemas/Error" } } } },
                        "402": { description: "Payment Required. PAYMENT-REQUIRED contains x402 requirements for 0.25 USDC on Base." },
                        "502": { description: "Evidence processing failed", content: { "application/json": { schema: { $ref: "#/components/schemas/Error" } } } },
                    },
                },
            },
        },
        components: {
            schemas: {
                TriggerPackRequest: {
                    type: "object",
                    additionalProperties: false,
                    required: ["company_domain", "goal"],
                    properties: {
                        company_domain: { type: "string", minLength: 3, maxLength: 2048, description: "Public company domain or HTTP(S) URL; private targets and custom ports are rejected." },
                        goal: { type: "string", minLength: 3, maxLength: 500, description: "Objective against which events are ranked." },
                        lookback_days: { type: "integer", minimum: 1, maximum: 90, default: 90 },
                    },
                },
                Evidence: {
                    type: "object",
                    additionalProperties: false,
                    required: ["id", "source_type", "source_url", "title", "published_at", "excerpt", "source_quality"],
                    properties: {
                        id: { type: "string" },
                        source_type: { type: "string", enum: ["company", "news", "jobs", "github", "regulatory", "other"] },
                        source_url: { type: "string", format: "uri" },
                        title: { type: "string" },
                        published_at: { type: ["string", "null"], format: "date-time" },
                        excerpt: { type: "string" },
                        source_quality: { type: "number", minimum: 0, maximum: 1 },
                    },
                },
                Trigger: {
                    type: "object",
                    additionalProperties: false,
                    required: ["id", "type", "event", "published_at", "why_it_matters", "relevance_to_goal", "confidence", "evidence_ids", "score"],
                    properties: {
                        id: { type: "string" },
                        type: { type: "string", enum: triggerTypes },
                        event: { type: "string", description: "Factual statement extracted from cited evidence." },
                        published_at: { type: ["string", "null"], format: "date-time" },
                        why_it_matters: { type: "string", description: "Grounded inference, not an observed fact." },
                        relevance_to_goal: { type: "number", minimum: 0, maximum: 1 },
                        confidence: { type: "number", minimum: 0, maximum: 1 },
                        evidence_ids: { type: "array", minItems: 1, items: { type: "string" } },
                        score: { type: "integer", minimum: 0, maximum: 100 },
                    },
                },
                TriggerPackResponse: {
                    type: "object",
                    required: ["request_id", "observed_at", "company", "best_trigger", "other_triggers", "action", "evidence", "diagnostics"],
                    properties: {
                        request_id: { type: "string", format: "uuid" },
                        observed_at: { type: "string", format: "date-time" },
                        company: { type: "object", required: ["name", "domain", "confidence"], properties: { name: { type: ["string", "null"] }, domain: { type: "string" }, confidence: { type: "number", minimum: 0, maximum: 1 } } },
                        best_trigger: { anyOf: [{ $ref: "#/components/schemas/Trigger" }, { type: "null" }] },
                        other_triggers: { type: "array", items: { $ref: "#/components/schemas/Trigger" } },
                        action: { type: "object", required: ["score", "recommendation", "reason", "angle"], properties: { score: { type: "integer" }, recommendation: { type: "string", enum: ["act_now", "monitor", "skip"] }, reason: { type: "string" }, angle: { type: ["string", "null"] } } },
                        evidence: { type: "array", items: { $ref: "#/components/schemas/Evidence" } },
                        diagnostics: { type: "object", required: ["sources_checked", "dated_sources_found", "runtime_ms"], properties: { sources_checked: { type: "integer" }, dated_sources_found: { type: "integer" }, runtime_ms: { type: "integer" }, cache_hit: { type: "boolean" }, upstream_errors: { type: "array", items: { type: "string" } } } },
                    },
                },
                Error: { type: "object", required: ["error", "message"], properties: { error: { type: "string" }, message: { type: "string" }, details: {} } },
            },
        },
    };
}

};

__modules["/index.ts"] = function(module, exports, require) {
"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const npm_hono_4_9_8_1 = require("npm:hono@4.9.8");
const hono_2_23_0_1 = require("npm:@x402/hono@2.23.0");
const server_1 = require("npm:@x402/core@2.23.0/server");
const server_2 = require("npm:@x402/evm@2.23.0/exact/server");
const request_ts_1 = require("./request.ts");
const engine_ts_1 = require("./engine.ts");
const openapi_ts_1 = require("./openapi.ts");
const NETWORK = "eip155:8453";
const DEFAULT_PRICE_USD = "0.25";
const DEFAULT_FACILITATOR_URL = "https://facilitator.xpay.sh";
const FUNCTION_SLUG = "triggerpack-public";
function emptyRuntimeConfig() {
    return {
        receiver: null,
        facilitatorUrl: DEFAULT_FACILITATOR_URL,
        priceUsd: DEFAULT_PRICE_USD,
        internalSmokeSecret: null,
    };
}
async function loadRuntimeConfig() {
    const supabaseUrl = Deno.env.get("SUPABASE_URL");
    const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
    if (!supabaseUrl || !serviceRoleKey)
        return emptyRuntimeConfig();
    try {
        const response = await fetch(`${supabaseUrl}/rest/v1/triggerpack_runtime_config?select=receiver_evm_address,facilitator_url,price_usd,internal_smoke_secret&singleton=eq.true&limit=1`, {
            headers: {
                apikey: serviceRoleKey,
                authorization: `Bearer ${serviceRoleKey}`,
                accept: "application/json",
            },
            signal: AbortSignal.timeout(4_000),
        });
        if (!response.ok)
            throw new Error(`runtime configuration HTTP ${response.status}`);
        const rows = await response.json();
        const row = rows[0] ?? {};
        const candidate = row.receiver_evm_address?.trim() ?? "";
        const receiver = /^0x[a-fA-F0-9]{40}$/.test(candidate)
            ? candidate
            : null;
        const numericPrice = Number(row.price_usd ?? DEFAULT_PRICE_USD);
        const priceUsd = Number.isFinite(numericPrice) && numericPrice > 0
            ? numericPrice.toFixed(2)
            : DEFAULT_PRICE_USD;
        const internalSmokeSecret = row.internal_smoke_secret?.trim() || null;
        return {
            receiver,
            facilitatorUrl: row.facilitator_url?.trim() || DEFAULT_FACILITATOR_URL,
            priceUsd,
            internalSmokeSecret,
        };
    }
    catch (error) {
        console.error(JSON.stringify({
            event: "triggerpack.runtime_config_failed",
            message: error instanceof Error ? error.message : String(error),
        }));
        return emptyRuntimeConfig();
    }
}
const runtimeConfig = await loadRuntimeConfig();
const PRICE = `$${runtimeConfig.priceUsd}`;
const app = new npm_hono_4_9_8_1.Hono();
function functionBase(requestUrl) {
    const url = new URL(requestUrl);
    const marker = `/${FUNCTION_SLUG}`;
    const index = url.pathname.indexOf(marker);
    url.pathname = index >= 0 ? url.pathname.slice(0, index + marker.length) : marker;
    url.search = "";
    url.hash = "";
    return url.toString().replace(/\/$/, "");
}
app.use("*", async (c, next) => {
    c.header("access-control-allow-origin", "*");
    c.header("access-control-allow-headers", "content-type,payment-signature,payment-required,x-payment,x-payment-response,x-triggerpack-internal-secret");
    c.header("access-control-expose-headers", "payment-required,payment-response,x-payment-response");
    c.header("access-control-allow-methods", "GET,POST,OPTIONS");
    c.header("cache-control", "no-store");
    c.header("x-content-type-options", "nosniff");
    if (c.req.method === "OPTIONS")
        return c.body(null, 204);
    await next();
});
if (runtimeConfig.receiver) {
    const facilitatorClient = new server_1.HTTPFacilitatorClient({ url: runtimeConfig.facilitatorUrl });
    const resourceServer = new hono_2_23_0_1.x402ResourceServer(facilitatorClient)
        .register(NETWORK, new server_2.ExactEvmScheme());
    app.use((0, hono_2_23_0_1.paymentMiddleware)({
        [`POST /${FUNCTION_SLUG}/v1/company-trigger-pack`]: {
            accepts: {
                scheme: "exact",
                price: PRICE,
                network: NETWORK,
                payTo: runtimeConfig.receiver,
                maxTimeoutSeconds: 60,
            },
            description: "Evidence-backed recent company triggers ranked against a supplied goal.",
            mimeType: "application/json",
        },
        "POST /v1/company-trigger-pack": {
            accepts: {
                scheme: "exact",
                price: PRICE,
                network: NETWORK,
                payTo: runtimeConfig.receiver,
                maxTimeoutSeconds: 60,
            },
            description: "Evidence-backed recent company triggers ranked against a supplied goal.",
            mimeType: "application/json",
        },
    }, resourceServer, undefined, undefined, false));
}
async function businessHandler(c) {
    let body;
    try {
        body = await c.req.json();
    }
    catch {
        return c.json({ error: "invalid_json", message: "Request body must be valid JSON." }, 400);
    }
    const parsed = request_ts_1.triggerPackRequestSchema.safeParse(body);
    if (!parsed.success) {
        return c.json({
            error: "invalid_request",
            message: "Request body does not match the published schema.",
            details: parsed.error.flatten(),
        }, 400);
    }
    try {
        const result = await (0, engine_ts_1.generateTriggerPack)(parsed.data);
        console.info(JSON.stringify({
            event: "triggerpack.completed",
            request_id: result.request_id,
            domain: result.company.domain,
            runtime_ms: result.diagnostics.runtime_ms,
            sources_checked: result.diagnostics.sources_checked,
            trigger_count: (result.best_trigger ? 1 : 0) + result.other_triggers.length,
        }));
        return c.json(result, 200);
    }
    catch (error) {
        const message = error instanceof Error ? error.message : "Unexpected processing failure";
        const inputError = /domain|URL|host|port|IP address/i.test(message);
        console.error(JSON.stringify({ event: "triggerpack.failed", message }));
        return c.json({
            error: inputError ? "invalid_company_domain" : "processing_failed",
            message,
        }, inputError ? 400 : 502);
    }
}
async function paidHandler(c) {
    if (!runtimeConfig.receiver) {
        return c.json({
            error: "payment_not_configured",
            message: "A confirmed owner-controlled public EVM receiving address is required before payments can be enabled.",
        }, 503);
    }
    return businessHandler(c);
}
app.post(`/${FUNCTION_SLUG}/v1/company-trigger-pack`, paidHandler);
app.post("/v1/company-trigger-pack", paidHandler);
app.post(`/${FUNCTION_SLUG}/internal/engine`, async (c) => {
    const supplied = c.req.header("x-triggerpack-internal-secret");
    if (!runtimeConfig.internalSmokeSecret || supplied !== runtimeConfig.internalSmokeSecret) {
        return c.json({ error: "not_found", message: "Route not found." }, 404);
    }
    return businessHandler(c);
});
function rootPayload(requestUrl) {
    const base = functionBase(requestUrl);
    return {
        name: "TriggerPack",
        description: "Evidence-backed recent company action triggers for autonomous agents.",
        paid_endpoint: `${base}/v1/company-trigger-pack`,
        openapi: `${base}/openapi.json`,
        health: `${base}/health`,
        discovery: `${base}/.well-known/x402`,
        price: `${runtimeConfig.priceUsd} USDC`,
        network: NETWORK,
        payment_configured: Boolean(runtimeConfig.receiver),
    };
}
for (const path of [`/${FUNCTION_SLUG}`, `/${FUNCTION_SLUG}/`, "/"]) {
    app.get(path, (c) => c.json(rootPayload(c.req.url)));
}
for (const path of [`/${FUNCTION_SLUG}/health`, "/health"]) {
    app.get(path, (c) => c.json({
        status: runtimeConfig.receiver ? "ok" : "degraded",
        service: "triggerpack",
        version: "0.1.0-edge",
        observed_at: new Date().toISOString(),
        runtime: "supabase-edge",
        payment: {
            configured: Boolean(runtimeConfig.receiver),
            protocol: "x402",
            price: PRICE,
            network: NETWORK,
            facilitator: runtimeConfig.facilitatorUrl,
        },
    }));
}
for (const path of [`/${FUNCTION_SLUG}/openapi.json`, "/openapi.json"]) {
    app.get(path, (c) => c.json((0, openapi_ts_1.buildOpenApi)(functionBase(c.req.url))));
}
for (const path of [`/${FUNCTION_SLUG}/.well-known/x402`, `/${FUNCTION_SLUG}/.well-known/x402.json`, "/.well-known/x402", "/.well-known/x402.json"]) {
    app.get(path, (c) => {
        const base = functionBase(c.req.url);
        return c.json({
            x402Version: 2,
            resources: [{
                    url: `${base}/v1/company-trigger-pack`,
                    method: "POST",
                    description: "Evidence-backed recent company triggers ranked against a supplied goal.",
                    accepts: runtimeConfig.receiver
                        ? [{
                                scheme: "exact",
                                network: NETWORK,
                                price: PRICE,
                                payTo: runtimeConfig.receiver,
                            }]
                        : [],
                }],
        });
    });
}
for (const path of [`/${FUNCTION_SLUG}/llms.txt`, "/llms.txt"]) {
    app.get(path, (c) => {
        const base = functionBase(c.req.url);
        return c.text(`# TriggerPack\n\nTriggerPack finds evidence-backed recent company events that create a defensible reason to act now.\n\n- Paid endpoint: POST ${base}/v1/company-trigger-pack\n- OpenAPI: ${base}/openapi.json\n- Price: ${runtimeConfig.priceUsd} USDC on Base via x402\n- Input: company_domain, goal, optional lookback_days\n- Output: ranked triggers, dated evidence, confidence and action recommendation\n`, 200, { "content-type": "text/plain; charset=utf-8" });
    });
}
app.notFound((c) => c.json({ error: "not_found", message: "Route not found.", ...rootPayload(c.req.url) }, 404));
app.onError((error, c) => {
    console.error(JSON.stringify({ event: "triggerpack.unhandled", message: error.message }));
    return c.json({ error: "internal_error", message: "Unexpected server error." }, 500);
});
Deno.serve(app.fetch);

};

__require('/bootstrap.ts', './index.ts');
