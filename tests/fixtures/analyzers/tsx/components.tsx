type Props = {
    enabled: boolean;
    items: Array<{ active: boolean; name: string }>;
};

export const UserCard = (props: Props) => {
    const click = () => props.enabled && track(props.items.length);
    return (
        <div onClick={() => props.enabled && track(1)}>
            {props.enabled ? <Panel /> : <Empty />}
            {props.items.map(item => {
                if (item.active) return <span>{item.name}</span>;
                return null;
            })}
        </div>
    );
};
