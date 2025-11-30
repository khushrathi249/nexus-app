import flet as ft
import sqlite3
import webbrowser

def main(page: ft.Page):
    page.title = "Nexus AI Viewer"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0
    page.bgcolor = "#f0f2f5"  
    
    # State
    current_category = "All" 
    current_search = ""

    # --- CONSTANTS ---
    # Only show map UI for these categories
    MAP_RELEVANT_CATEGORIES = ["Travel", "Food", "Recipe", "Restaurant", "Event", "Hiking", "Inbox"]

    # --- DATABASE FUNCTIONS ---
    def get_categories():
        try:
            conn = sqlite3.connect("nexus.db")
            c = conn.cursor()
            c.execute("SELECT DISTINCT category FROM links")
            cats = [row[0] for row in c.fetchall()]
            conn.close()
            base_cats = []
            for c in cats:
                if c and c != "Inbox" and c != "All": 
                    base_cats.append(c)
            return sorted(base_cats)
        except:
            return []

    def get_links(category="All", search_query=""):
        try:
            conn = sqlite3.connect("nexus.db")
            c = conn.cursor()
            
            # Base Query
            query = "SELECT id, title, image_url, url, category, ai_summary, lat, lon FROM links WHERE 1=1"
            params = []

            # Filter by Category
            if category != "All":
                query += " AND category = ?"
                params.append(category)

            # Filter by Search (Title or AI Summary)
            if search_query:
                query += " AND (title LIKE ? OR ai_summary LIKE ?)"
                wildcard = f"%{search_query}%"
                params.append(wildcard)
                params.append(wildcard)

            query += " ORDER BY id DESC"
            
            c.execute(query, tuple(params))
            data = c.fetchall()
            conn.close()
            return data
        except Exception as e:
            print(f"DB Error: {e}")
            return []

    def delete_link_db(link_id):
        conn = sqlite3.connect("nexus.db")
        c = conn.cursor()
        c.execute("DELETE FROM links WHERE id=?", (link_id,))
        conn.commit()
        conn.close()

    # --- UI COMPONENTS ---
    
    grid = ft.GridView(
        expand=True,
        runs_count=4,          
        max_extent=350,        
        child_aspect_ratio=0.7, 
        spacing=15,
        run_spacing=15,
        padding=20,
    )

    rail = ft.NavigationRail(
        selected_index=0,
        label_type=ft.NavigationRailLabelType.ALL,
        min_width=100,
        min_extended_width=200,
        group_alignment=-0.9,
        destinations=[],
        bgcolor="white"
    )

    def open_url(url):
        webbrowser.open(url)
        
    def open_map(lat, lon):
        if lat and lon:
            webbrowser.open(f"https://www.google.com/maps/search/?api=1&query={lat},{lon}")

    def delete_click(e, link_id):
        delete_link_db(link_id)
        refresh_app()

    # --- DETAILED SUMMARY MODAL ---
    def show_summary_dialog(title, summary, category, lat=None, lon=None):
        content_controls = [
            ft.Markdown(
                summary, 
                selectable=True,
                extension_set=ft.MarkdownExtensionSet.GITHUB_WEB
            )
        ]
        
        # LOGIC UPDATE: Only show map button if category allows it AND coords exist
        show_map = (lat and lon) and (category in MAP_RELEVANT_CATEGORIES)
        
        if show_map:
            content_controls.insert(0, 
                ft.Container(
                    content=ft.ElevatedButton(
                        "Open Location in Google Maps",
                        icon=ft.Icons.MAP,
                        style=ft.ButtonStyle(bgcolor=ft.Colors.GREEN_100, color=ft.Colors.GREEN_800),
                        on_click=lambda e: open_map(lat, lon)
                    ),
                    padding=ft.padding.only(bottom=10)
                )
            )

        dlg = ft.AlertDialog(
            title=ft.Text(title, size=20, weight="bold"),
            content=ft.Container(
                width=500,
                height=400,
                content=ft.Column(content_controls, scroll="adaptive")
            ),
        )
        page.open(dlg)

    def build_card(row):
        link_id, title, img_url, url, category, ai_summary, lat, lon = row
        
        # Robust Float Conversion
        try:
            lat = float(lat) if lat is not None else None
            lon = float(lon) if lon is not None else None
        except:
            lat, lon = None, None

        # LOGIC UPDATE: Strict Category Check for Map Pin
        has_geo_data = lat is not None and lon is not None
        is_relevant_cat = category in MAP_RELEVANT_CATEGORIES
        show_map_pin = has_geo_data and is_relevant_cat
        
        return ft.Card(
            elevation=0,
            content=ft.Container(
                bgcolor="white",
                border_radius=12,
                content=ft.Column(
                    spacing=0,
                    controls=[
                        # Image Section
                        ft.Container(
                            height=150,
                            content=ft.Image(
                                src=img_url if img_url else "https://placehold.co/600x400",
                                width=float("inf"),
                                height=150,
                                fit=ft.ImageFit.COVER,
                                border_radius=ft.border_radius.only(top_left=12, top_right=12),
                            ),
                            on_click=lambda e: open_url(url)
                        ),
                        # Text Content
                        ft.Container(
                            padding=12,
                            expand=True,
                            content=ft.Column(
                                spacing=4,
                                scroll="hidden",
                                controls=[
                                    ft.Row([
                                        ft.Container(
                                            content=ft.Text(str(category).upper(), size=10, weight="bold", color="white"),
                                            bgcolor="blue" if category != "Inbox" else "grey",
                                            padding=ft.padding.symmetric(horizontal=6, vertical=2),
                                            border_radius=4
                                        ),
                                        ft.Container(expand=True),
                                        # Visual Pin (Conditional)
                                        ft.Row([
                                            ft.Icon(ft.Icons.PIN_DROP, size=14, color="red"),
                                            ft.Text("Map", size=10, color="red", weight="bold")
                                        ], spacing=2) if show_map_pin else ft.Container()
                                    ]),
                                    ft.Text(title, weight="bold", size=14, max_lines=2, overflow="ellipsis", color="#1c1e21"),
                                ]
                            )
                        ),
                        # Action Buttons
                        ft.Container(
                            padding=10,
                            content=ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.TextButton(
                                        "View Note", 
                                        icon=ft.Icons.ANALYTICS_OUTLINED, 
                                        on_click=lambda e: show_summary_dialog(title, ai_summary, category, lat, lon)
                                    ) if ai_summary else ft.Container(),
                                    
                                    ft.IconButton(
                                        icon=ft.Icons.DELETE_OUTLINE_ROUNDED, 
                                        icon_color="#ff4757",
                                        icon_size=18,
                                        on_click=lambda e: delete_click(e, link_id)
                                    )
                                ]
                            )
                        )
                    ]
                )
            )
        )

    def refresh_app():
        links = get_links(current_category, current_search)
        grid.controls.clear()
        for row in links:
            grid.controls.append(build_card(row))
        
        if not links:
            msg = f"No links in {current_category}"
            if current_search: msg += f" matching '{current_search}'"
            grid.controls.append(ft.Text(msg, color="grey"))
        
        update_sidebar()
        page.update()

    def update_sidebar():
        dests = [
            ft.NavigationRailDestination(
                icon=ft.Icons.DASHBOARD_OUTLINED, 
                selected_icon=ft.Icons.DASHBOARD_SHARP, 
                label="All"
            ),
        ]
        
        cats = get_categories() 
        for c in cats:
            icon = ft.Icons.FOLDER_OUTLINED
            if c == "Recipe": icon = ft.Icons.RESTAURANT
            elif c == "Travel": icon = ft.Icons.AIRPLANE_TICKET
            elif c == "Tech": icon = ft.Icons.COMPUTER
            elif c == "Education": icon = ft.Icons.SCHOOL
            elif c == "Fitness": icon = ft.Icons.FITNESS_CENTER
            
            dests.append(
                ft.NavigationRailDestination(
                    icon=icon, 
                    label=c
                )
            )
        rail.destinations = dests
        if rail.page:
            rail.update()

    def on_nav_change(e):
        index = e.control.selected_index
        cats = get_categories()
        nonlocal current_category
        
        if index == 0:
            current_category = "All"
        else:
            cat_index = index - 1
            if cat_index < len(cats):
                current_category = cats[cat_index]
        refresh_app()
    
    def on_search(e):
        nonlocal current_search
        current_search = e.control.value
        refresh_app()

    rail.on_change = on_nav_change

    # Search Bar Component
    search_bar = ft.TextField(
        hint_text="Search titles or AI notes...",
        prefix_icon=ft.Icons.SEARCH,
        border_radius=10,
        bgcolor="white",
        on_change=on_search,
        height=40,
        content_padding=10,
        text_size=14
    )

    page.add(
        ft.Row(
            [
                rail,
                ft.VerticalDivider(width=1),
                ft.Column([ 
                    ft.Container(height=20),
                    ft.Row([
                        ft.Text("Nexus AI", size=24, weight="bold"),
                        ft.Container(expand=True),
                        ft.Container(width=300, content=search_bar, padding=ft.padding.only(right=20))
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Divider(color="transparent", height=10),
                    grid 
                ], expand=True),
            ],
            expand=True,
        )
    )

    update_sidebar()
    refresh_app()

ft.app(target=main)