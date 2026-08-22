export function Card({ enabled, items }) {
    return (
        <div>
            <section>
                <article>
                    {enabled && <Panel />}
                    {enabled ? <Panel /> : <Empty />}
                    {items.map(item => item.visible && <span>{item.name}</span>)}
                </article>
            </section>
        </div>
    );
}
