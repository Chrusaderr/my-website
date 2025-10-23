const coins = ["bitcoin", "ethereum", "litecoin", "dogecoin"];
const tableBody = document.getElementById("crypto-table");
const refreshSelect = document.getElementById("refresh");

let intervalId;

async function fetchPrices() {
    const response = await fetch(
        `https://api.coingecko.com/api/v3/simple/price?ids=${coins.join(",")}&vs_currencies=usd&include_24hr_change=true`
    );
    const data = await response.json();

    tableBody.innerHTML = "";

    coins.forEach(coin => {
        const price = data[coin].usd.toFixed(2);
        const change = data[coin].usd_24h_change.toFixed(2);
        const row = document.createElement("tr");

        row.innerHTML = `
            <td>${coin.charAt(0).toUpperCase() + coin.slice(1)}</td>
            <td>$${price}</td>
            <td class="${change >= 0 ? 'positive' : 'negative'}">${change}%</td>
        `;

        tableBody.appendChild(row);
    });
}

function startAutoRefresh() {
    if (intervalId) clearInterval(intervalId);
    fetchPrices();
    const interval = parseInt(refreshSelect.value);
    intervalId = setInterval(fetchPrices, interval);
}

refreshSelect.addEventListener("change", startAutoRefresh);
startAutoRefresh();