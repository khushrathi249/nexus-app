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
                if c and c != "Inbox": 
                    base_cats.append(c)
            return base_cats
        except:
            return []

    def get_links(category="All"):
        try:
            conn = sqlite3.connect("nexus.db")
            c = conn.cursor()
            if category == "All":
                c.execute("SELECT id, title, image_url, url, category, ai_summary FROM links ORDER BY id DESC")
            else:
                c.execute("SELECT id, title, image_url, url, category, ai_summary FROM links WHERE category=? ORDER BY id DESC", (category,))
            data = c.fetchall()
            conn.close()
            return data
        except Exception as e:
            print(e)
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

    # RE-ADDED MISSING COMPONENT
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

    def delete_click(e, link_id):
        delete_link_db(link_id)
        refresh_app()

    def build_card(row):
        link_id, title, img_url, url, category, ai_summary = row
        
        has_map = ai_summary and "maps.google.com" in ai_summary
        
        ai_section = ft.Container()
        if ai_summary:
            ai_section = ft.Container(
                bgcolor="#e3f2fd",
                padding=10,
                border_radius=8,
                margin=ft.margin.only(top=5),
                content=ft.Column([
                    ft.Text("✨ Nexus AI Analysis", size=10, weight="bold", color="blue"),
                    ft.Markdown(
                        ai_summary, 
                        selectable=True,
                        extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                        on_tap_link=lambda e: open_url(e.data)
                    )
                ])
            )

        return ft.Card(
            elevation=0,
            content=ft.Container(
                bgcolor="white",
                border_radius=12,
                content=ft.Column(
                    spacing=0,
                    controls=[
                        ft.Container(
                            height=140,
                            content=ft.Image(
                                src=img_url if img_url else "https://placehold.co/600x400",
                                width=float("inf"),
                                height=140,
                                fit=ft.ImageFit.COVER,
                                border_radius=ft.border_radius.only(top_left=12, top_right=12),
                            ),
                            on_click=lambda e: open_url(url)
                        ),
                        ft.Container(
                            padding=12,
                            expand=True,
                            content=ft.Column(
                                spacing=4,
                                scroll="hidden",
                                controls=[
                                    ft.Row([
                                        ft.Text(str(category).upper(), size=10, weight="bold", color="grey"),
                                        ft.Container(expand=True),
                                        ft.Icon(ft.Icons.MAP, size=16, color="green") if has_map else ft.Container()
                                    ]),
                                    ft.Text(title, weight="bold", size=14, max_lines=2, overflow="ellipsis", color="#1c1e21"),
                                    ai_section,
                                ]
                            )
                        ),
                        ft.Container(
                            padding=8,
                            content=ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.TextButton("Open Link", on_click=lambda e: open_url(url)),
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
            ft.NavigationRailDestination(
                icon=ft.Icons.INBOX_OUTLINED,
                selected_icon=ft.Icons.INBOX_SHARP,
                label="Inbox"
            )
        ]
        
        cats = get_categories() 
        for c in cats:
            dests.append(
                ft.NavigationRailDestination(
                    icon=ft.Icons.FOLDER_OUTLINED, 
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
        elif index == 1:
            current_category = "Inbox"
        else:
            cat_index = index - 2
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