import flet as ft
import sqlite3
import webbrowser

def main(page: ft.Page):
    page.title = "Nexus AI"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0
    page.bgcolor = "#f0f2f5"  
    
    current_category = "All" 

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

    def get_links(category="All"):
        try:
            conn = sqlite3.connect("nexus.db")
            c = conn.cursor()
            # UPDATED QUERY: Now fetches lat and lon
            if category == "All":
                c.execute("SELECT id, title, image_url, url, category, ai_summary, lat, lon FROM links ORDER BY id DESC")
            else:
                c.execute("SELECT id, title, image_url, url, category, ai_summary, lat, lon FROM links WHERE category=? ORDER BY id DESC", (category,))
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
    def show_summary_dialog(title, summary, lat=None, lon=None):
        content_controls = [
            ft.Markdown(
                summary, 
                selectable=True,
                extension_set=ft.MarkdownExtensionSet.GITHUB_WEB
            )
        ]
        
        if lat and lon:
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
        
        # DEBUG: Treat 0.0 as invalid, ensure float
        try:
            lat = float(lat) if lat is not None else None
            lon = float(lon) if lon is not None else None
        except:
            lat, lon = None, None

        has_geo = lat is not None and lon is not None
        
        # DEBUG TEXT: To prove to user if data exists
        geo_debug_text = f"Lat: {lat:.2f}" if has_geo else "No Geo"

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
                                        # Visual Pin
                                        ft.Row([
                                            ft.Icon(ft.Icons.PIN_DROP, size=14, color="red"),
                                            ft.Text("Map", size=10, color="red", weight="bold")
                                        ], spacing=2) if has_geo else ft.Container()
                                    ]),
                                    ft.Text(title, weight="bold", size=14, max_lines=2, overflow="ellipsis", color="#1c1e21"),
                                    # DEBUG: Show coordinates to user (Comment this out later)
                                    ft.Text(geo_debug_text, size=9, color="grey"),
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
                                        on_click=lambda e: show_summary_dialog(title, ai_summary, lat, lon)
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
        links = get_links(current_category)
        grid.controls.clear()
        for row in links:
            grid.controls.append(build_card(row))
        
        if not links:
            grid.controls.append(ft.Text(f"No links in {current_category}", color="grey"))
        
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

    rail.on_change = on_nav_change

    page.add(
        ft.Row(
            [
                rail,
                ft.VerticalDivider(width=1),
                ft.Column([ 
                    ft.Container(height=20),
                    ft.Text("Nexus AI", size=24, weight="bold"),
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