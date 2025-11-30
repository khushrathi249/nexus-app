import flet as ft
import sqlite3
import webbrowser

def main(page: ft.Page):
    page.title = "Nexus"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0
    page.bgcolor = "#f0f2f5"  
    
    current_category = "All" 

    def get_categories():
        conn = sqlite3.connect("nexus.db") # Pointing to new DB
        c = conn.cursor()
        c.execute("SELECT DISTINCT category FROM links")
        cats = [row[0] for row in c.fetchall()]
        conn.close()
        base_cats = ["Inbox"]
        for c in cats:
            if c != "Inbox": base_cats.append(c)
        return base_cats

    def get_links(category="All"):
        try:
            conn = sqlite3.connect("nexus.db")
            c = conn.cursor()
            if category == "All":
                c.execute("SELECT id, title, image_url, url, category FROM links ORDER BY id DESC")
            else:
                c.execute("SELECT id, title, image_url, url, category FROM links WHERE category=? ORDER BY id DESC", (category,))
            data = c.fetchall()
            conn.close()
            return data
        except:
            return []

    def delete_link_db(link_id):
        conn = sqlite3.connect("nexus.db")
        c = conn.cursor()
        c.execute("DELETE FROM links WHERE id=?", (link_id,))
        conn.commit()
        conn.close()

    grid = ft.GridView(
        expand=True,
        runs_count=5,          
        max_extent=300,        
        child_aspect_ratio=0.75, 
        spacing=15,
        run_spacing=15,
        padding=20,
    )

    def open_url(url):
        webbrowser.open(url)

    def delete_click(e, link_id):
        delete_link_db(link_id)
        refresh_app()

    def build_card(row):
        link_id, title, img_url, url, category = row
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
                                controls=[
                                    ft.Text(category.upper(), size=10, weight="bold", color="blue"),
                                    ft.Text(title, weight="bold", size=13, max_lines=2, overflow="ellipsis", color="#1c1e21"),
                                    ft.Text(url, size=10, color="grey", italic=True, max_lines=1, overflow="ellipsis"),
                                ]
                            )
                        ),
                        ft.Container(
                            padding=8,
                            content=ft.Row(
                                alignment=ft.MainAxisAlignment.END,
                                controls=[
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

    def on_nav_change(e):
        index = e.control.selected_index
        cats = get_categories()
        nonlocal current_category
        if index == 0:
            current_category = "All"
        else:
            cats.insert(0, "Inbox")
            real_cats = get_categories() 
            if index - 1 < len(real_cats):
                current_category = real_cats[index-1]
        refresh_app()

    rail = ft.NavigationRail(
        selected_index=0,
        label_type=ft.NavigationRailLabelType.ALL,
        min_width=100,
        min_extended_width=400,
        group_alignment=-0.9,
        destinations=[],
        on_change=on_nav_change,
        bgcolor="white"
    )

    def update_sidebar():
        dests = [
            ft.NavigationRailDestination(
                icon=ft.Icons.DASHBOARD_OUTLINED, 
                selected_icon=ft.Icons.DASHBOARD_SHARP, 
                label="All"
            )
        ]
        cats = get_categories() 
        for c in cats:
            icon = ft.Icons.FOLDER_OUTLINED
            if c == "Inbox": icon = ft.Icons.INBOX_OUTLINED
            dests.append(
                ft.NavigationRailDestination(
                    icon_content=ft.Icon(icon),
                    label=c
                )
            )
        rail.destinations = dests

    update_sidebar()
    refresh_app()

    page.add(
        ft.Row(
            [
                rail,
                ft.VerticalDivider(width=1),
                ft.Column([ 
                    ft.Container(height=20),
                    ft.Text("Nexus Stacks", size=24, weight="bold"),
                    ft.Divider(color="transparent", height=10),
                    grid 
                ], expand=True),
            ],
            expand=True,
        )
    )

ft.app(target=main)