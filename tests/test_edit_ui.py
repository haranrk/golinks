"""Playwright tests for the /edit config editor UI."""

import json
import subprocess
import time

import pytest
from playwright.sync_api import expect, sync_playwright

SERVER_PORT = 9222
BASE_URL = f"http://127.0.0.1:{SERVER_PORT}"
CONFIG_PATH = "config.json"

ORIGINAL_CONFIG = {
    "github": "https://github.com",
    "mail": "https://gmail.com",
    "calendar": "https://calendar.google.com",
}


@pytest.fixture(scope="module")
def server():
    """Start the golinks server for testing."""
    proc = subprocess.Popen(
        ["uv", "run", "golinks", "run-server", "--port", str(SERVER_PORT), "--config", CONFIG_PATH],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    time.sleep(1)
    yield proc
    proc.terminate()
    proc.wait()


@pytest.fixture(scope="module")
def browser_context(server):
    """Create a shared browser context."""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context()
        yield context
        context.close()
        browser.close()


@pytest.fixture()
def page(browser_context):
    page = browser_context.new_page()
    yield page
    page.close()


@pytest.fixture(autouse=True)
def _restore_config():
    """Restore original config after each test."""
    yield
    with open(CONFIG_PATH, "w") as f:
        json.dump(ORIGINAL_CONFIG, f, indent=2)
        f.write("\n")


def test_edit_page_loads(page):
    """Edit page loads with existing links rendered as cards."""
    page.goto(f"{BASE_URL}/edit")
    expect(page.locator("h1")).to_have_text("Edit Go Links")
    cards = page.locator(".link-card")
    expect(cards).to_have_count(3)


def test_existing_links_show_correct_values(page):
    """Each card has the correct shortcut and URL."""
    page.goto(f"{BASE_URL}/edit")
    # Links are sorted alphabetically: calendar, github, mail
    names = page.locator('input[data-field="name"]')
    expect(names.nth(0)).to_have_value("calendar")
    expect(names.nth(1)).to_have_value("github")
    expect(names.nth(2)).to_have_value("mail")


def test_add_link(page):
    """Clicking Add Link creates a new empty card."""
    page.goto(f"{BASE_URL}/edit")
    expect(page.locator(".link-card")).to_have_count(3)
    page.click("#add-link-btn")
    expect(page.locator(".link-card")).to_have_count(4)
    # New card's name input should be focused and empty
    new_name = page.locator('.link-card:last-child input[data-field="name"]')
    expect(new_name).to_have_value("")


def test_delete_link(page):
    """Clicking Delete removes a link card."""
    page.goto(f"{BASE_URL}/edit")
    expect(page.locator(".link-card")).to_have_count(3)
    # Delete the first link
    page.locator(".link-card").first.locator("button.btn-danger").click()
    expect(page.locator(".link-card")).to_have_count(2)


def test_save_after_adding_link(page):
    """Add a new link and save; config file should be updated."""
    page.goto(f"{BASE_URL}/edit")
    page.click("#add-link-btn")
    # Fill in the new link (last card)
    last_card = page.locator(".link-card").last
    last_card.locator('input[data-field="name"]').fill("test")
    last_card.locator('input[data-field="url"]').fill("https://example.com")
    page.click("#save-btn")
    # Wait for success message
    expect(page.locator(".message-success")).to_be_visible()

    with open(CONFIG_PATH) as f:
        saved = json.load(f)
    assert saved["test"] == "https://example.com"
    # Original links still present
    assert saved["github"] == "https://github.com"


def test_save_after_deleting_link(page):
    """Delete a link and save; it should be gone from config."""
    page.goto(f"{BASE_URL}/edit")
    # Delete "calendar" (first card since sorted)
    page.locator(".link-card").first.locator("button.btn-danger").click()
    page.click("#save-btn")
    expect(page.locator(".message-success")).to_be_visible()

    with open(CONFIG_PATH) as f:
        saved = json.load(f)
    assert "calendar" not in saved
    assert "github" in saved


def test_edit_existing_link(page):
    """Edit a link's URL and save."""
    page.goto(f"{BASE_URL}/edit")
    # Edit github URL (second card, index 1)
    url_input = page.locator('input[data-field="url"]').nth(1)
    url_input.fill("https://github.com/myorg")
    page.click("#save-btn")
    expect(page.locator(".message-success")).to_be_visible()

    with open(CONFIG_PATH) as f:
        saved = json.load(f)
    assert saved["github"] == "https://github.com/myorg"


def test_template_toggle_shows_defaults(page):
    """Toggling Template checkbox shows the defaults section."""
    page.goto(f"{BASE_URL}/edit")
    first_card = page.locator(".link-card").first
    # Should not have defaults section initially
    expect(first_card.locator(".defaults-section")).to_have_count(0)
    # Toggle template on
    first_card.locator('input[type="checkbox"]').check()
    expect(first_card.locator(".defaults-section")).to_have_count(1)


def test_save_template_link(page):
    """Create a template link with defaults and save."""
    page.goto(f"{BASE_URL}/edit")
    page.click("#add-link-btn")
    last_card = page.locator(".link-card").last

    last_card.locator('input[data-field="name"]').fill("search")
    last_card.locator('input[data-field="url"]').fill("https://google.com/search?q={1}")
    last_card.locator('input[type="checkbox"]').check()

    # Add a default — fill value first, then key (key change triggers re-render)
    last_card.locator("button", has_text="+ Add Default").click()
    last_card.locator('input[data-field="default-value"]').fill("python")
    last_card.locator('input[data-field="default-key"]').fill("1")
    # Blur to trigger the change event and re-render
    last_card.locator('input[data-field="default-key"]').blur()

    page.click("#save-btn")
    expect(page.locator(".message-success")).to_be_visible()

    with open(CONFIG_PATH) as f:
        saved = json.load(f)
    assert saved["search"]["template_url"] == "https://google.com/search?q={1}"
    assert saved["search"]["defaults"]["1"] == "python"


def test_save_empty_name_shows_error(page):
    """Saving a link without a name shows an error."""
    page.goto(f"{BASE_URL}/edit")
    page.click("#add-link-btn")
    # Leave name empty, fill URL
    last_card = page.locator(".link-card").last
    last_card.locator('input[data-field="url"]').fill("https://example.com")
    page.click("#save-btn")
    expect(page.locator(".message-error")).to_be_visible()


def test_saved_link_redirects(page):
    """A newly saved link actually works as a redirect."""
    page.goto(f"{BASE_URL}/edit")
    page.click("#add-link-btn")
    last_card = page.locator(".link-card").last
    last_card.locator('input[data-field="name"]').fill("mytest")
    last_card.locator('input[data-field="url"]').fill("https://example.com")
    page.click("#save-btn")
    expect(page.locator(".message-success")).to_be_visible()

    response = page.goto(f"{BASE_URL}/mytest")
    assert response.url.startswith("https://example.com")


def test_empty_state_shows_when_all_deleted(page):
    """Deleting all links shows empty state."""
    page.goto(f"{BASE_URL}/edit")
    # Delete all 3 links
    for _ in range(3):
        page.locator(".link-card").first.locator("button.btn-danger").click()
    expect(page.locator(".link-card")).to_have_count(0)
    expect(page.locator("#empty-state")).to_be_visible()
